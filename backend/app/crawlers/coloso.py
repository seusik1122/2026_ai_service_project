"""콜로소 크롤러 — 디자인/창작/비즈니스."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger

# 주요 카테고리 ID (콜로소는 숫자 ID 기반)
TOP_CATEGORIES = [
    ("드로잉/일러스트", "https://coloso.co.kr/category/1"),
    ("디지털아트",      "https://coloso.co.kr/category/2"),
    ("사진/영상",       "https://coloso.co.kr/category/3"),
    ("디자인",          "https://coloso.co.kr/category/12"),
    ("비즈니스",        "https://coloso.co.kr/category/47"),
    ("3D/모션",         "https://coloso.co.kr/category/48"),
    ("음악",            "https://coloso.co.kr/category/53"),
    ("웹툰/만화",       "https://coloso.co.kr/category/73"),
    ("크래프트",        "https://coloso.co.kr/category/377"),
]


class ColosoCrawler:
    PLATFORM = "coloso"

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = await ctx.new_page()
            try:
                categories = await self._get_categories(page)
                logger.info(f"콜로소 카테고리: {len(categories)}개")

                for cat_name, cat_url in categories:
                    logger.info(f"콜로소 크롤링: {cat_name}")
                    try:
                        items = await self._crawl_category(page, cat_name, cat_url)
                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"콜로소 DB 저장 실패: {item.get('title')} — {e}")
                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    except Exception as e:
                        logger.error(f"콜로소 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"콜로소 완료: {len(collected)}건")
        return collected

    async def _get_categories(self, page) -> list[tuple[str, str]]:
        try:
            await page.goto("https://coloso.co.kr/categories/all", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            cat_links = await page.eval_on_selector_all(
                'a[href*="/category/"]',
                'els => [...new Map(els.map(e => [e.href, {text: e.innerText.trim(), href: e.href}])).values()]'
            )
            result = []
            seen = set()
            for c in cat_links:
                text = c["text"].strip()
                href = c["href"].split("?")[0]
                if not text or href in seen or len(text) < 1:
                    continue
                # 숫자 ID 카테고리만 (서브카테고리 제외)
                if re.search(r'/category/\d+$', href):
                    seen.add(href)
                    result.append((text, href))
            return result if result else list(TOP_CATEGORIES)
        except Exception as e:
            logger.warning(f"콜로소 카테고리 목록 실패, fallback: {e}")
            return list(TOP_CATEGORIES)

    async def _crawl_category(self, page, cat_name: str, cat_url: str) -> list[dict]:
        await page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # 스크롤로 무한스크롤 트리거
        for _ in range(8):
            await page.keyboard.press("End")
            await page.wait_for_timeout(1200)

        # 강의 링크 수집 — /products/{slug} 패턴
        links = await page.eval_on_selector_all(
            'a[href*="/products/"]',
            'els => [...new Map(els.map(e => [e.href.split("?")[0], {href: e.href.split("?")[0], text: e.innerText.trim()}])).values()]'
        )

        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"]
            if not text or href in seen:
                continue
            if any(k in href for k in ["event", "login", "cart"]):
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if not lines:
                continue

            title, instructor = self._parse_card_text(lines)
            if not title or len(title) < 3:
                continue

            price, is_free = self._extract_price(text)

            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
                "instructor_name": instructor,
                "category": cat_name,
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
    def _parse_card_text(lines: list[str]) -> tuple[str, Optional[str]]:
        # 콜로소 카드 구조: "제목\n강사명" 또는 "제목\n부제\n강사명"
        title = lines[0]
        instructor = None
        # 마지막 줄이 짧으면 강사명으로 취급
        if len(lines) >= 2:
            last = lines[-1]
            if 1 < len(last) <= 25 and not re.search(r'[%원₩]', last):
                instructor = last
        return title, instructor

    @staticmethod
    def _extract_price(text: str) -> tuple[Optional[int], bool]:
        if "무료" in text or "FREE" in text.upper():
            return 0, True
        m = re.search(r"([\d,]+)\s*원", text)
        if m:
            digits = m.group(1).replace(",", "")
            if digits:
                return int(digits), False
        return None, False
