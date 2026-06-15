"""베어유 / 퍼블리 / 폴인 크롤러 — 디자인/창작/자기계발."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class BearYuCrawler:
    """베어유 — 디자인/창작 온라인 클래스."""
    PLATFORM = "bearyu"
    URLS = [
        ("디자인/창작", "https://bearyu.com"),
        ("디자인/창작", "https://www.bearyu.co.kr"),
        ("디자인/창작", "https://bearyu.co.kr/courses"),
        ("디자인/창작", "https://bearyu.co.kr/category"),
    ]

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            page = await ctx.new_page()
            working_domain = None

            try:
                # 접근 가능한 도메인 탐색
                for cat_name, url in self.URLS:
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        await page.wait_for_timeout(2000)
                        html_len = len(await page.content())
                        if html_len > 5000:
                            working_domain = url.split("/")[0] + "//" + url.split("/")[2]
                            logger.info(f"베어유 접근 성공: {url} ({html_len}자)")
                            break
                    except Exception as e:
                        logger.warning(f"베어유 {url} 접근 실패: {e}")
                        continue

                if not working_domain:
                    logger.warning("베어유 접근 가능한 도메인 없음")
                    return collected

                items = await self._parse_page(page, "디자인/창작", working_domain)
                for item in items:
                    try:
                        upsert_lecture(LectureCreate(**item))
                        collected.append(item)
                    except Exception as e:
                        logger.error(f"베어유 DB 저장 실패: {e}")

                logger.info(f"  베어유: {len(items)}건")

            finally:
                await browser.close()

        logger.info(f"베어유 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str, domain: str) -> list[dict]:
        for _ in range(5):
            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)

        links = await page.eval_on_selector_all(
            'a[href]',
            'els => [...new Map(els.map(e => [e.href.split("?")[0], {href: e.href.split("?")[0], text: e.innerText.trim()}])).values()]'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or href in seen or len(text) < 3:
                continue
            if not any(d in href for d in ["bearyu.com", "bearyu.co.kr"]):
                continue
            if any(k in href for k in ["login", "event", "blog", "notice", "faq"]):
                continue
            if not any(k in href for k in ["course", "class", "product", "lecture", "detail"]):
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            instructor = self._extract_instructor(text)
            price, is_free = self._extract_price(text)

            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
                "instructor_name": instructor,
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
    def _extract_instructor(text: str) -> Optional[str]:
        for line in text.split("\n"):
            line = line.strip()
            if 2 <= len(line) <= 20 and not any(c.isdigit() for c in line):
                if not any(k in line for k in ["클래스", "강의", "과정", "원", "%"]):
                    return line
        return None

    @staticmethod
    def _extract_price(text: str) -> tuple[Optional[int], bool]:
        if "무료" in text or "FREE" in text.upper():
            return 0, True
        m = re.search(r"([\d,]+)\s*원", text)
        if m:
            return int(m.group(1).replace(",", "")), False
        return None, False


class PublyCrawler:
    """퍼블리 — 자기계발/커리어/인사이트 콘텐츠."""
    PLATFORM = "publy"
    CATEGORIES = [
        ("자기계발/인사이트", "https://publy.co/content"),
        ("커리어",           "https://publy.co/series"),
        ("템플릿",           "https://publy.co/template"),
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
                    logger.info(f"퍼블리 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)

                        for _ in range(8):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1200)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"퍼블리 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"퍼블리 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"퍼블리 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        links = await page.eval_on_selector_all(
            'a[href*="/content/"], a[href*="/series/"], a[href*="/template/"]',
            'els => [...new Map(els.map(e => [e.href.split("?")[0], {href: e.href.split("?")[0], text: e.innerText.trim()}])).values()]'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or href in seen or len(text) < 3:
                continue
            if "publy.co" not in href:
                continue
            if any(k in href for k in ["login", "signup"]):
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            # 작성자/강사
            instructor = None
            if len(lines) >= 2:
                last = lines[-1]
                if 2 <= len(last) <= 25 and not any(c.isdigit() for c in last):
                    instructor = last

            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
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


class FoleinCrawler:
    """폴인 — 자기계발/인사이트/비즈니스 콘텐츠."""
    PLATFORM = "folin"
    CATEGORIES = [
        ("자기계발/인사이트", "https://www.folin.co/story"),
        ("비즈니스",          "https://www.folin.co/series"),
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
                    logger.info(f"폴인 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)

                        for _ in range(8):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1200)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"폴인 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"폴인 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"폴인 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        links = await page.eval_on_selector_all(
            'a[href*="/story/"], a[href*="/series/"], a[href*="/book/"]',
            'els => [...new Map(els.map(e => [e.href.split("?")[0], {href: e.href.split("?")[0], text: e.innerText.trim()}])).values()]'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or href in seen or len(text) < 3:
                continue
            if "folin.co" not in href:
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            instructor = None
            if len(lines) >= 2:
                last = lines[-1]
                if 2 <= len(last) <= 25:
                    instructor = last

            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
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
