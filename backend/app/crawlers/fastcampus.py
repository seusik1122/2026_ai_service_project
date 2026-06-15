"""패스트캠퍼스 크롤러 — IT/개발/디자인/비즈니스."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger

# 카테고리 페이지 URL — fastcampus.co.kr/category_online_{key}
CATEGORIES = [
    ("IT/개발",       "https://fastcampus.co.kr/category_online_programming"),
    ("AI/데이터",     "https://fastcampus.co.kr/category_online_datasciencedl"),
    ("디자인",        "https://fastcampus.co.kr/category_online_dgn"),
    ("영상/3D",       "https://fastcampus.co.kr/category_online_video"),
    ("업무생산성",    "https://fastcampus.co.kr/category_online_biz"),
    ("AI/창작",       "https://fastcampus.co.kr/category_online_aicreative"),
]

# 강의 URL 패턴: dev_online_xxx, data_online_xxx, dgn_online_xxx 등
COURSE_URL_PREFIXES = ("_online_", "_red_", "_oneonone_", "fastcampus.co.kr/dev_", "fastcampus.co.kr/data_")


class FastcampusCrawler:
    PLATFORM = "fastcampus"

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = await ctx.new_page()
            try:
                for cat_name, url in CATEGORIES:
                    logger.info(f"패스트캠퍼스 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(6000)

                        for _ in range(6):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1500)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"패스트캠퍼스 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    except Exception as e:
                        logger.error(f"패스트캠퍼스 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"패스트캠퍼스 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        links = await page.eval_on_selector_all(
            'a[href]',
            'els => [...new Map(els.map(e => [e.href.split("?")[0], {href: e.href.split("?")[0], text: e.innerText.trim()}])).values()]'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or href in seen:
                continue
            if "fastcampus.co.kr" not in href:
                continue
            if any(k in href for k in ["javascript", "event", "login", "category_", "b2b", "info", "community", "story", "account", "openseminar", "onedayclass"]):
                continue
            # 강의 URL 패턴 매칭
            path = href.replace("https://fastcampus.co.kr/", "")
            if not any(sep in path for sep in ["_online_", "_red_", "_oneonone_", "_camp_"]):
                continue
            if len(path.split("/")) > 2:
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            price = self._extract_price(text)
            is_free = price == 0

            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
                "instructor_name": None,
                "category": category,
                "price": price,
                "rating": None,
                "student_count": None,
                "url": href,
                "thumbnail_url": None,
                "tags": None,
                "is_free": is_free,
            })
        return items

    @staticmethod
    def _extract_price(text: str) -> Optional[int]:
        if "무료" in text or "FREE" in text.upper():
            return 0
        m = re.search(r"([\d,]+)\s*원", text)
        if m:
            digits = m.group(1).replace(",", "")
            return int(digits) if digits else None
        return None
