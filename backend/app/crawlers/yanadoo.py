"""야나두/YBM/산타토익 크롤러 — 영어/어학 강의."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class YanadooCrawler:
    PLATFORM = "yanadoo"
    CATEGORIES = [
        ("영어회화",    "https://www.yanadoo.co.kr/store/english"),
        ("AI클래스",    "https://www.yanadoo.co.kr/store/ai"),
        ("커리어",      "https://www.yanadoo.co.kr/store/career"),
        ("전체강의",    "https://www.yanadoo.co.kr/store/list"),
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
                    logger.info(f"야나두 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(5000)

                        for _ in range(6):
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
                                logger.error(f"야나두 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"야나두 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"야나두 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str) -> list[dict]:
        links = await page.eval_on_selector_all(
            'a[href*="/store/detail/"]',
            'els => [...new Map(els.map(e => [e.href.split("?")[0], {href: e.href.split("?")[0], text: e.innerText.trim()}])).values()]'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or href in seen:
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = ""
            instructor = None
            cat_tag = category

            for line in lines:
                if not title and len(line) >= 5 and not re.search(r"^\d+\s*(클래스|강의)\s*포함", line):
                    title = line
                elif re.search(r"·|외\s*\d+명", line):
                    # "강민서 외 2명" 또는 "강민서"
                    m = re.match(r"([가-힣A-Za-z\s]+?)(?:\s*외\s*\d+명)?$", line.split("·")[-1].strip())
                    if m:
                        instructor = m.group(1).strip()
                elif any(k in line for k in ["AI", "영어", "커리어", "비즈니스", "생산성"]):
                    cat_tag = line

            if not title or len(title) < 3:
                continue

            price = self._extract_price(text)
            items.append({
                "platform": self.PLATFORM,
                "title": title[:200],
                "instructor_name": instructor,
                "category": cat_tag or category,
                "price": price,
                "rating": None,
                "student_count": None,
                "url": href,
                "thumbnail_url": None,
                "tags": None,
                "is_free": price == 0,
            })
        return items

    @staticmethod
    def _extract_price(text: str) -> Optional[int]:
        if "무료" in text:
            return 0
        m = re.search(r"([\d,]+)\s*원", text)
        if m:
            digits = m.group(1).replace(",", "")
            return int(digits) if digits else None
        return None


class YBMCrawler:
    PLATFORM = "ybm"
    CATEGORIES = [
        ("영어/토익",  "https://m.toeic.ybmclass.com/toeic/toeic_main.asp"),
        ("영어회화",   "https://m.eng.ybmclass.com/"),
        ("일본어",     "https://m.japan.ybmclass.com/"),
        ("중국어",     "https://m.china.ybmclass.com/"),
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
                    logger.info(f"YBM 크롤링: {cat_name}")
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
                                logger.error(f"YBM DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"YBM {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"YBM 완료: {len(collected)}건")
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
            if "ybmclass.com" not in href and "ybmnet.co.kr" not in href:
                continue
            if not any(k in href for k in ["/lec/", "/lecture/", "/detail", "/view/", "/teacher/", "_detail", "product_detail"]):
                continue
            if any(k in href for k in ["javascript", "login", "list?", "YBMSisacom", "classroom"]):
                continue
            if len(text) > 100:
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            instructor = None
            if len(lines) >= 2:
                last = lines[-1]
                if 2 <= len(last) <= 15 and not any(c.isdigit() for c in last):
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


class SantaToeicCrawler:
    PLATFORM = "santa_toeic"
    # 산타토익은 앱 중심이라 웹 콘텐츠가 제한적 — YBM santa 도메인 사용
    CATEGORIES = [
        ("토익", "https://www.santayoum.com/courses"),
        ("토익", "https://www.ybmsanta.com/courses"),
    ]

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            try:
                for cat_name, url in self.CATEGORIES:
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                        html = await page.content()
                        if len(html) < 3000:
                            continue

                        links = await page.eval_on_selector_all(
                            'a[href]',
                            'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))'
                        )
                        seen = set()
                        for link in links:
                            href = link["href"]
                            text = link["text"].strip()
                            if not text or href in seen or len(text) < 3:
                                continue
                            if any(k in href for k in ["javascript", "login"]):
                                continue
                            if not any(k in href for k in ["course", "lecture", "detail"]):
                                continue
                            seen.add(href)

                            lines = [l.strip() for l in text.split("\n") if l.strip()]
                            title = lines[0] if lines else text[:100]
                            if not title or len(title) < 3:
                                continue

                            try:
                                upsert_lecture(LectureCreate(
                                    platform=self.PLATFORM,
                                    title=title[:200],
                                    instructor_name=None,
                                    category=cat_name,
                                    price=None,
                                    rating=None,
                                    student_count=None,
                                    url=href,
                                    thumbnail_url=None,
                                    tags=["토익"],
                                    is_free=False,
                                ))
                                collected.append({"url": href, "title": title})
                            except Exception as e:
                                logger.error(f"산타토익 DB 저장 실패: {e}")
                        logger.info(f"  산타토익 {url}: {len(collected)}건")
                    except Exception as e:
                        logger.warning(f"산타토익 {url} 접근 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"산타토익 완료: {len(collected)}건")
        return collected
