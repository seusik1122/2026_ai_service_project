"""클래스101 크롤러 — 카테고리별 전체 강의 수집.

방식: Playwright로 카테고리 목록 페이지 파싱
- 카테고리 페이지에서 product 링크 + 카드 텍스트로 제목/강사/가격 추출
- 카테고리 177개를 순회하되, 상위(부모) 카테고리만 수집해 중복 최소화
"""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger

# 주요 상위 카테고리 fallback (동적 수집 실패 시 사용)
TOP_CATEGORIES = [
    ("드로잉",          "https://class101.net/ko/categories/604f1c9756c3676f1ed00304"),
    ("디지털 드로잉",   "https://class101.net/ko/categories/604f1c9756c3676f1ed0030e"),
    ("일러스트",        "https://class101.net/ko/categories/613070fa5b76158cac88344a"),
    ("공예",            "https://class101.net/ko/categories/604f1c9756c3676f1ed00317"),
    ("요리 · 음료",     "https://class101.net/ko/categories/604f1c9756c3676f1ed00341"),
    ("베이킹 · 디저트", "https://class101.net/ko/categories/604f1c9756c3676f1ed00346"),
    ("음악",            "https://class101.net/ko/categories/604f1c9756c3676f1ed0034e"),
    ("운동",            "https://class101.net/ko/categories/604f1c9756c3676f1ed00355"),
    ("사진 · 영상",     "https://class101.net/ko/categories/604f1c9756c3676f1ed00362"),
    ("글쓰기",          "https://class101.net/ko/categories/604f1c9756c3676f1ed00371"),
    ("재테크",          "https://class101.net/ko/categories/604f1c9756c3676f1ed00375"),
    ("자기계발",        "https://class101.net/ko/categories/604f1c9756c3676f1ed00380"),
    ("IT · 개발",       "https://class101.net/ko/categories/604f1c9756c3676f1ed00385"),
    ("디자인",          "https://class101.net/ko/categories/604f1c9756c3676f1ed00386"),
    ("언어",            "https://class101.net/ko/categories/604f1c9756c3676f1ed00387"),
    ("키즈",            "https://class101.net/ko/categories/604f1c9756c3676f1ed00388"),
]


class Class101Crawler:
    PLATFORM = "class101"

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
                categories = await self._get_all_categories(page)
                logger.info(f"클래스101 카테고리: {len(categories)}개")

                for cat_name, cat_url in categories:
                    logger.info(f"클래스101 크롤링: {cat_name}")
                    try:
                        items = await self._crawl_category(page, cat_name, cat_url)
                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"클래스101 DB 저장 실패: {item.get('title')} — {e}")
                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    except Exception as e:
                        logger.error(f"클래스101 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"클래스101 완료: {len(collected)}건")
        return collected

    async def _get_all_categories(self, page) -> list[tuple[str, str]]:
        try:
            await page.goto("https://class101.net/ko/categories", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            cats = await page.eval_on_selector_all(
                'a[href*="/ko/categories/"]',
                'els => [...new Map(els.map(e => [e.href.split("?")[0], {text: e.innerText.trim(), href: e.href.split("?")[0]}])).values()]'
            )
            result = []
            seen = set()
            for c in cats:
                text = c["text"].strip()
                href = c["href"]
                if not text or href in seen or len(text) < 2:
                    continue
                seen.add(href)
                result.append((text, href))
            return result if result else list(TOP_CATEGORIES)
        except Exception as e:
            logger.warning(f"클래스101 카테고리 목록 수집 실패, fallback 사용: {e}")
            return list(TOP_CATEGORIES)

    async def _crawl_category(self, page, cat_name: str, cat_url: str) -> list[dict]:
        await page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        for _ in range(5):
            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)

        cards = await page.query_selector_all('a[href*="/ko/products/"]')
        items = []
        seen = set()

        for card in cards:
            try:
                item = await self._parse_card(card, cat_name)
                if item and item.get("url") not in seen:
                    seen.add(item["url"])
                    items.append(item)
            except Exception as e:
                logger.error(f"클래스101 카드 파싱 오류: {e}")

        return items

    async def _parse_card(self, card, category: str) -> Optional[dict]:
        href = await card.get_attribute("href")
        if not href:
            return None
        url = f"https://class101.net{href}" if href.startswith("/") else href
        url = url.split("?")[0]

        text = (await card.inner_text()).strip()
        if not text:
            return None

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return None

        # 텍스트 구조: "순위\n제목\n재료태그 | 강사명" 또는 "제목\n재료태그 | 강사명"
        if lines[0].isdigit():
            title = lines[1] if len(lines) > 1 else ""
            remaining = lines[2:]
        else:
            title = lines[0]
            remaining = lines[1:]

        if not title or len(title) < 2:
            return None

        # 강사명 추출 — "재료태그 | 강사명" 패턴
        instructor = None
        for line in remaining:
            if "|" in line:
                parts = line.split("|")
                candidate = parts[-1].strip()
                if 1 < len(candidate) <= 30:
                    instructor = candidate
                break
        if not instructor and remaining:
            last = remaining[-1]
            if 1 < len(last) <= 20 and not any(c.isdigit() for c in last):
                instructor = last

        price, is_free = self._extract_price(text)

        img_el = await card.query_selector("img")
        thumbnail = await img_el.get_attribute("src") if img_el else None
        if thumbnail and "cdn.class101.net" not in thumbnail:
            thumbnail = None

        return {
            "platform": self.PLATFORM,
            "title": title[:200],
            "instructor_name": instructor,
            "category": category,
            "price": price,
            "rating": None,
            "student_count": None,
            "url": url,
            "thumbnail_url": thumbnail,
            "tags": None,
            "is_free": is_free,
        }

    @staticmethod
    def _extract_price(text: str) -> tuple[Optional[int], bool]:
        if "무료" in text or "FREE" in text.upper():
            return 0, True
        m = re.search(r"([\d,]+)\s*원", text)
        if m:
            return int(m.group(1).replace(",", "")), False
        return None, False
