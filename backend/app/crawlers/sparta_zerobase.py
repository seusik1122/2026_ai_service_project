"""스파르타코딩클럽 / 제로베이스 크롤러 — IT/개발."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class SpartaCrawler:
    PLATFORM = "spartacodingclub"
    CATEGORIES = [
        ("IT/개발", "https://spartacodingclub.kr/catalog"),
        ("AI/자동화", "https://spartacodingclub.kr/catalog?category=AI"),
        ("웹개발", "https://spartacodingclub.kr/catalog?category=web"),
        ("앱개발", "https://spartacodingclub.kr/catalog?category=app"),
        ("데이터", "https://spartacodingclub.kr/catalog?category=data"),
        ("게임", "https://spartacodingclub.kr/catalog?category=game"),
    ]

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
                for cat_name, url in self.CATEGORIES:
                    logger.info(f"스파르타 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)

                        for _ in range(5):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1000)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"스파르타 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"스파르타 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"스파르타 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        # spartacodingclub.kr 및 spartaclub.kr 링크 수집
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
            if not any(d in href for d in ["spartacodingclub.kr", "spartaclub.kr"]):
                continue
            if not any(k in href for k in ["/class/", "/course/", "/courses/", "/catalog/", "/kdc/"]):
                continue
            if any(k in href for k in ["login", "event", "blog", "community"]):
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            is_free = "무료" in text or "free" in text.lower()
            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
                "instructor_name": None,
                "category": category,
                "price": 0 if is_free else None,
                "rating": None,
                "student_count": None,
                "url": href,
                "thumbnail_url": None,
                "tags": ["무료"] if is_free else None,
                "is_free": is_free,
            })
        return items


class ZerobaseCrawler:
    PLATFORM = "zerobase"
    # 제로베이스는 JS 렌더링이 느려 Playwright + 충분한 대기 필요
    CATEGORIES = [
        ("IT/개발",   "https://zero-base.co.kr/category/dev"),
        ("디자인",    "https://zero-base.co.kr/category/design"),
        ("데이터",    "https://zero-base.co.kr/category/data"),
        ("마케팅",    "https://zero-base.co.kr/category/marketing"),
        ("비즈니스",  "https://zero-base.co.kr/category/business"),
    ]

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
                for cat_name, url in self.CATEGORIES:
                    logger.info(f"제로베이스 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        # JS 렌더링 충분히 대기
                        await page.wait_for_timeout(8000)

                        for _ in range(5):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1500)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"제로베이스 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"제로베이스 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"제로베이스 완료: {len(collected)}건")
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
            if "zero-base.co.kr" not in href:
                continue
            # placeholder 링크 제외
            if "[" in href or "]" in href:
                continue
            if any(k in href for k in ["event", "info", "login", "mailto"]):
                continue
            # 강의/커리큘럼 링크 패턴
            if not any(k in href for k in ["/category/", "/curriculum/", "/course/", "/courses/"]):
                continue
            # 카테고리 인덱스 페이지 제외
            if href.rstrip("/").endswith(("/dev", "/design", "/data", "/marketing", "/business")):
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
                "instructor_name": None,
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
