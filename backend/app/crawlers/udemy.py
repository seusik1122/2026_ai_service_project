"""유데미 크롤러 — 카테고리별 전체 페이지 수집."""
import re
import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class UdemyCrawler:
    PLATFORM = "udemy"
    CATEGORIES = [
        ("IT/개발",      "https://www.udemy.com/courses/development/web-development/?lang=ko&sort=highest-rated"),
        ("파이썬",       "https://www.udemy.com/courses/development/programming-languages/?lang=ko&sort=highest-rated"),
        ("데이터사이언스","https://www.udemy.com/courses/development/data-science/?lang=ko&sort=highest-rated"),
        ("모바일앱",     "https://www.udemy.com/courses/development/mobile-apps/?lang=ko&sort=highest-rated"),
        ("게임개발",     "https://www.udemy.com/courses/development/game-development/?lang=ko&sort=highest-rated"),
        ("AWS/클라우드", "https://www.udemy.com/courses/it-and-software/it-certifications/?lang=ko&sort=highest-rated"),
        ("네트워크/보안","https://www.udemy.com/courses/it-and-software/network-and-security/?lang=ko&sort=highest-rated"),
        ("디자인",       "https://www.udemy.com/courses/design/graphic-design/?lang=ko&sort=highest-rated"),
        ("사진/영상",    "https://www.udemy.com/courses/photography-and-video/?lang=ko&sort=highest-rated"),
        ("비즈니스",     "https://www.udemy.com/courses/business/?lang=ko&sort=highest-rated"),
        ("마케팅",       "https://www.udemy.com/courses/marketing/?lang=ko&sort=highest-rated"),
        ("자기계발",     "https://www.udemy.com/courses/personal-development/?lang=ko&sort=highest-rated"),
        ("음악",         "https://www.udemy.com/courses/music/?lang=ko&sort=highest-rated"),
        ("AI/머신러닝",  "https://www.udemy.com/courses/development/data-science/?lang=ko&subcategory=Machine+Learning&sort=highest-rated"),
    ]
    MAX_PAGES = 10  # 카테고리당 최대 페이지

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                      "--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                locale="ko-KR",
                extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
            )
            page = await ctx.new_page()
            try:
                for cat_name, base_url in self.CATEGORIES:
                    logger.info(f"유데미 카테고리: {cat_name}")
                    cat_total = 0
                    for page_num in range(1, self.MAX_PAGES + 1):
                        sep = "&" if "?" in base_url else "?"
                        url = f"{base_url}{sep}p={page_num}"
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(3000)
                        except Exception as e:
                            logger.warning(f"유데미 {cat_name} p{page_num} 로딩 실패: {e}")
                            break

                        items = await self._parse_page(page, cat_name)
                        if not items:
                            logger.info(f"  {cat_name} p{page_num}: 강의 없음 — 종료")
                            break

                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                            except Exception as e:
                                logger.error(f"유데미 DB 저장 실패: {item.get('title')} — {e}")

                        collected.extend(items)
                        cat_total += len(items)
                        logger.info(f"  {cat_name} p{page_num}: {len(items)}건")
                        await asyncio.sleep(random.uniform(2, 3))

                    logger.info(f"유데미 {cat_name} 완료: {cat_total}건")

            finally:
                await browser.close()

        logger.info(f"유데미 전체 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        # 유데미 카드 셀렉터 (여러 패턴 시도)
        for selector in [
            "div.course-card_container__urXwO",
            "div[class*='course-card']",
            "div[data-purpose='course-card']",
        ]:
            cards = await page.query_selector_all(selector)
            if cards:
                break

        items = []
        seen = set()
        for card in cards:
            try:
                item = await self._parse_card(card, category)
                if item and item.get("title") and item.get("url") not in seen:
                    seen.add(item.get("url"))
                    items.append(item)
            except Exception as e:
                logger.error(f"유데미 카드 파싱 오류: {e}")
        return items

    async def _parse_card(self, card, category: str) -> Optional[dict]:
        # 제목
        for sel in ["h3.ud-heading-md", "h3[class*='heading']", "div[class*='title']"]:
            title_el = await card.query_selector(sel)
            if title_el:
                break
        title = (await title_el.inner_text()).strip() if title_el else ""
        if not title:
            return None

        # 강사
        instructor = None
        for sel in ["div[data-purpose*='visible-instructors']", "span[class*='instructor']", "div[class*='instructor']"]:
            el = await card.query_selector(sel)
            if el:
                txt = (await el.inner_text()).strip()
                if txt:
                    instructor = txt[:100]
                    break

        # 평점
        rating = None
        for sel in ["span[data-purpose='rating-number']", "span[class*='rating-number']"]:
            el = await card.query_selector(sel)
            if el:
                try:
                    rating = float((await el.inner_text()).strip())
                except ValueError:
                    pass
                break

        # 수강생 수
        student_count = None
        for sel in ["span[data-purpose='enrollment-count']", "span[class*='enrollment']"]:
            el = await card.query_selector(sel)
            if el:
                student_count = self._parse_student_count((await el.inner_text()).strip())
                break

        # 가격
        price, is_free = None, False
        for sel in ["span[data-purpose='course-price-text']", "span[class*='price-text']", "div[class*='price']"]:
            el = await card.query_selector(sel)
            if el:
                price, is_free = self._parse_price((await el.inner_text()).strip())
                break

        # URL
        link_el = await card.query_selector("a[href*='/course/']")
        href = await link_el.get_attribute("href") if link_el else None
        url = f"https://www.udemy.com{href}" if href and href.startswith("/") else href

        # 썸네일
        img_el = await card.query_selector("img")
        thumbnail = await img_el.get_attribute("src") if img_el else None

        return {
            "platform": self.PLATFORM,
            "title": title,
            "instructor_name": instructor,
            "category": category,
            "price": price,
            "rating": rating,
            "student_count": student_count,
            "url": url,
            "thumbnail_url": thumbnail,
            "tags": None,
            "is_free": is_free,
        }

    @staticmethod
    def _parse_price(text: str) -> tuple[Optional[int], bool]:
        if not text or "무료" in text or "free" in text.lower():
            return 0, True
        digits = re.sub(r"[^\d]", "", text)
        return (int(digits), False) if digits else (None, False)

    @staticmethod
    def _parse_student_count(text: str) -> Optional[int]:
        if not text:
            return None
        text = text.replace(",", "").replace("명", "")
        m = re.search(r"\d+", text)
        return int(m.group()) if m else None
