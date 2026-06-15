"""메가스터디 크롤러 — 수능/공무원."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class MegastudyCrawler:
    PLATFORM = "megastudy"
    # 강의목록 URL: study_step 단계별 페이지
    CATEGORIES = [
        ("수능/국어", "http://www.megastudy.net/lecmain/mains/study_step/lecture_list.asp?mOne=step&mTwo=concept&CHR_GRD=3&SCH_CLS_TYPE=2&SCH_SUBJECT=1"),
        ("수능/수학", "http://www.megastudy.net/lecmain/mains/study_step/lecture_list.asp?mOne=step&mTwo=concept&CHR_GRD=3&SCH_CLS_TYPE=2&SCH_SUBJECT=2"),
        ("수능/영어", "http://www.megastudy.net/lecmain/mains/study_step/lecture_list.asp?mOne=step&mTwo=concept&CHR_GRD=3&SCH_CLS_TYPE=2&SCH_SUBJECT=3"),
        ("수능/사탐", "http://www.megastudy.net/lecmain/mains/study_step/lecture_list.asp?mOne=step&mTwo=concept&CHR_GRD=3&SCH_CLS_TYPE=2&SCH_SUBJECT=4"),
        ("수능/과탐", "http://www.megastudy.net/lecmain/mains/study_step/lecture_list.asp?mOne=step&mTwo=concept&CHR_GRD=3&SCH_CLS_TYPE=2&SCH_SUBJECT=5"),
        ("수능기초",  "http://www.megastudy.net/lecmain/mains/study_step/lecture_list.asp?mOne=step&mTwo=basics&CHR_GRD=3&SCH_CLS_TYPE=1"),
        ("공무원",   "http://www.megastudy.net/gosi/list.asp?gb=gosi"),
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
                    logger.info(f"메가스터디 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)

                        items = await self._parse_page(page, cat_name)
                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"메가스터디 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        logger.error(f"메가스터디 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"메가스터디 완료: {len(collected)}건")
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
            if "megastudy.net" not in href:
                continue
            if "javascript" in href or "#" in href:
                continue
            # 강의 상세 링크 패턴
            if not any(k in href for k in ["lecture_detailview", "chr_detail", "view", "lec_seq", "t_idx", "CHR_CD"]):
                continue
            if len(text) > 120:
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

    @staticmethod
    def _extract_instructor(text: str) -> Optional[str]:
        # "강민철의" → "강민철"
        m = re.search(r"([가-힣]{2,4})(?:의|쌤|T|선생님|강사)", text)
        return m.group(1) if m else None
