"""생활코딩 + 노마드코더 크롤러."""
import re
import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger


class OpentutorialsCrawler:
    """생활코딩 (opentutorials.org) — IT 무료 강의."""
    PLATFORM = "opentutorials"
    COURSE_LIST_URL = "https://opentutorials.org/course"

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
            try:
                logger.info("생활코딩 크롤링 시작")
                await page.goto(self.COURSE_LIST_URL, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                links = await page.eval_on_selector_all(
                    'a[href*="/course/"]',
                    'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))'
                )
                seen = set()
                for link in links:
                    href = link["href"]
                    title = link["text"]
                    if not title or href in seen or len(title) < 2:
                        continue
                    seen.add(href)
                    item = {
                        "platform": self.PLATFORM,
                        "title": title[:200],
                        "instructor_name": "이고잉",
                        "category": "IT/개발",
                        "price": 0,
                        "rating": None,
                        "student_count": None,
                        "url": href,
                        "thumbnail_url": None,
                        "tags": ["무료", "입문"],
                        "is_free": True,
                    }
                    try:
                        upsert_instructor("이고잉", self.PLATFORM)
                        upsert_lecture(LectureCreate(**item))
                        collected.append(item)
                    except Exception as e:
                        logger.error(f"생활코딩 DB 저장 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"생활코딩 완료: {len(collected)}건")
        return collected


class NomadcoderCrawler:
    """노마드코더 — IT 강의."""
    PLATFORM = "nomadcoder"
    COURSES_URL = "https://nomadcoders.co/courses"
    SKIP_PATHS = {"/", "/courses", "/challenges", "/reviews", "/community",
                  "/roadmap", "/supaplate", "/faq", "/login", "/join", "/register"}

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
            try:
                logger.info("노마드코더 크롤링 시작")
                await page.goto(self.COURSES_URL, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                links = await page.eval_on_selector_all(
                    'a[href]',
                    'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))'
                )
                seen = set()
                for link in links:
                    href = link["href"]
                    text = link["text"]
                    if not href or not text:
                        continue
                    # nomadcoders.co/강의슬러그 형태만
                    if "nomadcoders.co/" not in href:
                        continue
                    path = href.replace("https://nomadcoders.co", "")
                    if path in self.SKIP_PATHS or path.startswith("/login") or path.startswith("/join"):
                        continue
                    if href in seen:
                        continue
                    seen.add(href)

                    # 제목과 설명 분리 (줄바꿈 기준)
                    parts = [p.strip() for p in text.split("\n") if p.strip()]
                    title = parts[0] if parts else text[:100]
                    if len(title) < 2:
                        continue

                    is_free = "무료" in text or "FREE" in text.upper() or "free" in text.lower()

                    item = {
                        "platform": self.PLATFORM,
                        "title": title[:200],
                        "instructor_name": "니꼬쌤",
                        "category": "IT/개발",
                        "price": 0 if is_free else None,
                        "rating": None,
                        "student_count": None,
                        "url": href,
                        "thumbnail_url": None,
                        "tags": ["무료"] if is_free else None,
                        "is_free": is_free,
                    }
                    try:
                        upsert_instructor("니꼬쌤", self.PLATFORM)
                        upsert_lecture(LectureCreate(**item))
                        collected.append(item)
                    except Exception as e:
                        logger.error(f"노마드코더 DB 저장 실패: {e}")

            finally:
                await browser.close()

        logger.info(f"노마드코더 완료: {len(collected)}건")
        return collected
