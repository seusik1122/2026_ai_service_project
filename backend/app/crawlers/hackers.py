"""해커스 크롤러 — 공무원/토익/어학/자격증."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class HackersCrawler:
    PLATFORM = "hackers"
    CATEGORIES = [
        ("공무원",     "https://gosi.hackers.com/academy/lecture_list"),
        ("토익",       "https://www.hackers.ac/site/?st=lecture&idx=201"),
        ("토스/오픽",  "https://www.hackers.ac/site/?st=lecture&idx=203"),
        ("텝스",       "https://www.hackers.ac/site/?st=lecture&idx=204"),
        ("경찰공무원", "https://police.hackers.com/academy/lecture_list"),
        ("소방공무원", "https://fire.hackers.com/site/?c=lecture"),
        ("한국사",     "https://history.hackers.com/lecture/list"),
        ("편입",       "https://www.hackers.com/lecture/list"),
        ("어학원영어", "https://www.hackersingang.com/course/list"),
    ]

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            try:
                for cat_name, url in self.CATEGORIES:
                    logger.info(f"해커스 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(3000)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"해커스 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"해커스 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"해커스 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        # 강의 카드 셀렉터 탐색 (해커스 계열 사이트마다 다름)
        items = []
        seen = set()

        # 방법 1: 강의 카드 직접 파싱
        for card_sel in [
            "div.lec_list_item", "li.lecture_item", "div.course_item",
            "ul.lecture_list li", "div[class*='lecture'] li",
            "table.lecture_table tr",
        ]:
            cards = await page.query_selector_all(card_sel)
            if cards:
                for card in cards:
                    try:
                        item = await self._parse_card(card, category, page.url)
                        if item and item.get("title") and item.get("url") not in seen:
                            seen.add(item.get("url"))
                            items.append(item)
                    except Exception as e:
                        logger.error(f"해커스 카드 파싱 오류: {e}")
                if items:
                    return items

        # 방법 2: 링크 기반 fallback
        links = await page.eval_on_selector_all(
            'a[href]',
            'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))'
        )
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or len(text) < 5 or href in seen:
                continue
            if not any(k in href for k in ["lecture", "course", "class", "lec_"]):
                continue
            if any(k in href for k in ["javascript", "login", "#"]):
                continue
            if len(text) > 80:
                continue
            seen.add(href)

            instructor = self._extract_instructor(text)
            items.append({
                "platform": self.PLATFORM,
                "title": text[:200],
                "instructor_name": instructor,
                "category": category,
                "price": None,
                "rating": None,
                "student_count": None,
                "url": href,
                "thumbnail_url": None,
                "tags": None,
                "is_free": False,
            })
        return items

    async def _parse_card(self, card, category: str, base_url: str) -> Optional[dict]:
        # 제목
        title = ""
        for sel in ["p.tit", "span.tit", "strong.tit", "h3", "h4", "td.subject", "div.title"]:
            el = await card.query_selector(sel)
            if el:
                title = (await el.inner_text()).strip()
                break
        if not title:
            title = (await card.inner_text()).strip().split("\n")[0]
        if not title or len(title) < 3:
            return None

        # 강사
        instructor = None
        for sel in ["span.teacher", "span.name", "p.teacher", "td.teacher", "div.teacher"]:
            el = await card.query_selector(sel)
            if el:
                instructor = (await el.inner_text()).strip()
                break
        if not instructor:
            instructor = self._extract_instructor(title)

        # URL
        link_el = await card.query_selector("a[href]")
        href = await link_el.get_attribute("href") if link_el else None
        if href and href.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"
        url = href

        # 가격
        price, is_free = None, False
        for sel in ["span.price", "p.price", "td.price", "div.price"]:
            el = await card.query_selector(sel)
            if el:
                price, is_free = self._parse_price((await el.inner_text()).strip())
                break

        return {
            "platform": self.PLATFORM,
            "title": title[:200],
            "instructor_name": instructor,
            "category": category,
            "price": price,
            "rating": None,
            "student_count": None,
            "url": url,
            "thumbnail_url": None,
            "tags": None,
            "is_free": is_free,
        }

    @staticmethod
    def _extract_instructor(text: str) -> Optional[str]:
        m = re.search(r"([가-힣]{2,4})\s*(선생님|쌤|강사)", text)
        return m.group(1) if m else None

    @staticmethod
    def _parse_price(text: str) -> tuple[Optional[int], bool]:
        if not text or "무료" in text:
            return 0, True
        digits = re.sub(r"[^\d]", "", text)
        return (int(digits), False) if digits else (None, False)
