"""EBSi/이투스 크롤러 — 수능 무료/유료 강의."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class EBSiCrawler:
    PLATFORM = "ebsi"
    CATEGORIES = [
        ("수능 전체",   "https://www.ebsi.co.kr/ebs/lms/subMain/subMain.ebs?cookieGradeVal=high3"),
        ("수능/국어",   "https://www.ebsi.co.kr/ebs/pot/potn/retrieveTchrSubMain.ebs"),
        ("수능/한국사", "https://www.ebsi.co.kr/ebs/pot/potn/retrieveTchrSubMain.ebs?tabIdx=3"),
        ("수능/시리즈", "https://www.ebsi.co.kr/ebs/pot/potg/SeriesInfoPsList.ebs"),
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
                    logger.info(f"EBSi 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)

                        for _ in range(5):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1000)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"EBSi DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"EBSi {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"EBSi 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        links = await page.eval_on_selector_all(
            'a[href]',
            'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or len(text) < 3 or href in seen:
                continue
            if "ebsi.co.kr" not in href:
                continue
            if "javascript" in href or href.endswith("#") or href.endswith("#none;"):
                continue
            if not any(k in href for k in ["lec", "course", "Lec", "Tchr", "tchr", "subjectId", "SeriesInfo", "Subject"]):
                continue
            if len(text) > 100:
                continue
            seen.add(href)

            instructor = self._extract_instructor(text)
            items.append({
                "platform": self.PLATFORM,
                "title": text[:200],
                "instructor_name": instructor,
                "category": category,
                "price": 0,
                "rating": None,
                "student_count": None,
                "url": href,
                "thumbnail_url": None,
                "tags": ["무료", "수능"],
                "is_free": True,
            })
        return items

    @staticmethod
    def _extract_instructor(text: str) -> Optional[str]:
        m = re.search(r"([가-힣]{2,4})\s*(선생님|쌤|T\b|강사)", text)
        return m.group(1) if m else None


class EtoossCrawler:
    PLATFORM = "etoos"
    CATEGORIES = [
        ("수능/국어",   "https://www.etoos.com/lec/list.asp?subject=01"),
        ("수능/수학",   "https://www.etoos.com/lec/list.asp?subject=02"),
        ("수능/영어",   "https://www.etoos.com/lec/list.asp?subject=03"),
        ("수능/사탐",   "https://www.etoos.com/lec/list.asp?subject=04"),
        ("수능/과탐",   "https://www.etoos.com/lec/list.asp?subject=05"),
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
                    logger.info(f"이투스 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)

                        for _ in range(5):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1000)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"이투스 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"이투스 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"이투스 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        links = await page.eval_on_selector_all(
            'a[href]',
            'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or len(text) < 3 or href in seen:
                continue
            if "etoos.com" not in href:
                continue
            if not any(k in href for k in ["lec", "lecture", "detail", "view", "teacher"]):
                continue
            if any(k in href for k in ["javascript", "login", "list.asp"]):
                continue
            if len(text) > 100:
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
                "tags": ["수능"],
                "is_free": False,
            })
        return items

    @staticmethod
    def _extract_instructor(text: str) -> Optional[str]:
        m = re.search(r"([가-힣]{2,4})\s*(선생님|쌤|T\b|강사)", text)
        return m.group(1) if m else None
