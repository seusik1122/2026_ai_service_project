"""시원스쿨 크롤러 — 어학 강의."""
import re
import asyncio
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class SiwonschoolCrawler:
    PLATFORM = "siwonschool"
    CATEGORIES = [
        ("영어", "https://www.siwonschool.com/english/"),
        ("중국어", "https://www.siwonschool.com/chinese/"),
        ("일본어", "https://www.siwonschool.com/japanese/"),
        ("제2외국어", "https://www.siwonschool.com/language/"),
    ]

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
            try:
                for category, url in self.CATEGORIES:
                    logger.info(f"시원스쿨 크롤링: {category}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(2000)

                        # 강의 링크 수집 — /lecture/ 포함 URL
                        links = await page.eval_on_selector_all(
                            'a[href*="lecture"], a[href*="course"], a[href*="class"]',
                            'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))'
                        )

                        # h4.tch_lec 강의명도 수집
                        cards = await page.query_selector_all("h4.tch_lec")
                        titles_from_cards = []
                        for card in cards:
                            txt = (await card.inner_text()).strip()
                            if txt:
                                titles_from_cards.append(txt)

                        seen = set()
                        items = []

                        # 링크 기반 수집
                        for link in links:
                            href = link["href"]
                            text = link["text"]
                            if not text or len(text) < 3 or href in seen:
                                continue
                            seen.add(href)
                            items.append({
                                "platform": self.PLATFORM,
                                "title": text[:200],
                                "instructor_name": "이시원" if category == "영어" else None,
                                "category": category,
                                "price": None,
                                "rating": None,
                                "student_count": None,
                                "url": href,
                                "thumbnail_url": None,
                                "tags": None,
                                "is_free": False,
                            })

                        # 카드 기반 수집 (링크 없는 경우)
                        for title in titles_from_cards:
                            if title not in seen and len(title) > 3:
                                seen.add(title)
                                items.append({
                                    "platform": self.PLATFORM,
                                    "title": title[:200],
                                    "instructor_name": "이시원" if category == "영어" else None,
                                    "category": category,
                                    "price": None,
                                    "rating": None,
                                    "student_count": None,
                                    "url": url,
                                    "thumbnail_url": None,
                                    "tags": None,
                                    "is_free": False,
                                })

                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"시원스쿨 DB 저장 실패: {e}")

                        logger.info(f"  {category}: {len(items)}건")
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"시원스쿨 {category} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"시원스쿨 완료: 총 {len(collected)}건")
        return collected
