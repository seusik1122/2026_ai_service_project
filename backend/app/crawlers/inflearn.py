"""인프런 크롤러 — BeautifulSoup HTML 파싱 방식."""
import re
import asyncio
import random
from typing import Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class InflearnCrawler:
    PLATFORM = "inflearn"
    CATEGORIES = [
        ("it-programming",          "IT/개발"),
        ("artificial-intelligence", "AI/머신러닝"),
        ("data-science",            "데이터사이언스"),
        ("game-dev-all",            "게임개발"),
        ("design",                  "디자인"),
        ("foreign-language",        "어학"),
        ("business",                "비즈니스"),
        ("productivity",            "업무생산성"),
        ("academics",               "학문"),
        ("hardware",                "하드웨어"),
        ("Applied-ai",              "AI활용"),
        ("it",                      "IT자격증"),
        ("career",                  "커리어"),
    ]
    BASE_URL = "https://www.inflearn.com/courses/{category}?sort=POPULAR&page={page}"

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            try:
                for cat_slug, cat_name in self.CATEGORIES:
                    logger.info(f"인프런 카테고리: {cat_name}")
                    cat_total = 0
                    page_num = 1
                    cat_seen_urls: set[str] = set()
                    while True:
                        url = self.BASE_URL.format(category=cat_slug, page=page_num)
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_selector("article.mantine-Card-root", timeout=15000, state="attached")
                            await page.wait_for_timeout(2000)
                        except Exception as e:
                            logger.warning(f"인프런 {cat_name} p{page_num} 로딩 실패: {e}")
                            break

                        html = await page.content()
                        items = self._parse_html(html, cat_name)
                        if not items:
                            logger.info(f"  {cat_name} p{page_num}: 강의 없음 — 종료")
                            break

                        # 중복 페이지 감지 (인프런은 비로그인 시 일정 페이지 이후 순환)
                        new_items = [i for i in items if i["url"] not in cat_seen_urls]
                        if not new_items:
                            logger.info(f"  {cat_name} p{page_num}: 중복 — 종료")
                            break

                        for item in new_items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                cat_seen_urls.add(item["url"])
                            except Exception as e:
                                logger.error(f"인프런 DB 저장 실패: {item.get('title')} — {e}")

                        collected.extend(new_items)
                        cat_total += len(new_items)
                        logger.info(f"  {cat_name} p{page_num}: {len(new_items)}건 (누계 {cat_total}건)")

                        last_page = self._get_last_page(html)
                        if last_page and page_num >= last_page:
                            break
                        page_num += 1
                        await asyncio.sleep(random.uniform(1, 2))

                    logger.info(f"인프런 {cat_name} 완료: {cat_total}건")

            finally:
                await browser.close()

        logger.info(f"인프런 전체 완료: {len(collected)}건")
        return collected

    def _parse_html(self, html: str, category: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        items = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=re.compile(r"inflearn\.com/course/")):
            href = a.get("href", "").split("?")[0].strip()
            if not href or href in seen:
                continue
            seen.add(href)

            title_p = a.find("p", class_=re.compile(r"fcy4ne"))
            if not title_p:
                for p in a.find_all("p"):
                    txt = p.get_text(strip=True)
                    if len(txt) > 5:
                        title_p = p
                        break
            title = title_p.get_text(strip=True) if title_p else ""
            if not title:
                continue

            instructor_p = a.find("p", class_=re.compile(r"mantine-ai[a-z0-9]"))
            instructor = instructor_p.get_text(strip=True) if instructor_p else None

            all_text = a.get_text(separator=" ")

            rating_m = re.search(r"(\d\.\d)\s*\((\d[\d,]*)\)", all_text)
            rating = float(rating_m.group(1)) if rating_m else None
            review_count = int(rating_m.group(2).replace(",", "")) if rating_m else None

            student_m = re.search(r"([\d,]+)명", all_text)
            student_count = int(student_m.group(1).replace(",", "")) if student_m else review_count

            price_m = re.search(r"([\d,]+)원", all_text)
            if "무료" in all_text and not price_m:
                price, is_free = 0, True
            elif price_m:
                price = int(price_m.group(1).replace(",", ""))
                is_free = price == 0
            else:
                price, is_free = None, False

            img = a.find("img")
            thumbnail = img.get("src") if img else None

            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
                "instructor_name": instructor,
                "category": category,
                "price": price,
                "rating": rating,
                "student_count": student_count,
                "url": href,
                "thumbnail_url": thumbnail,
                "tags": None,
                "is_free": is_free,
            })
        return items

    @staticmethod
    def _get_last_page(html: str) -> Optional[int]:
        soup = BeautifulSoup(html, "html.parser")
        nums = []
        for btn in soup.find_all("button"):
            txt = btn.get_text(strip=True)
            if txt.isdigit():
                nums.append(int(txt))
        return max(nums) if nums else None
