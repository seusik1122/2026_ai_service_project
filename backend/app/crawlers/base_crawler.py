import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright
from fake_useragent import UserAgent
from app.db.queries import upsert_lecture
from app.db.models import LectureCreate
from app.utils.logger import logger


class BaseCrawler:
    """모든 플랫폼 크롤러의 베이스 클래스.

    - Playwright(chromium) 브라우저 lifecycle 관리
    - fake_useragent 랜덤 User-Agent
    - 실패 시 최대 3회 재시도 후 logger.error()
    - DB 저장은 queries.py 함수(upsert_lecture)를 통해서만 수행
    """

    MAX_RETRIES: int = 3

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.ua: UserAgent = UserAgent()

    async def init_browser(self) -> None:
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-software-rasterizer",
            ],
        )

    async def fetch_page(
        self,
        url: str,
        retries: Optional[int] = None,
        wait_selector: Optional[str] = None,
        timeout: int = 30000,
    ) -> str:
        """페이지 HTML을 반환. 실패 시 최대 retries회 재시도 후 빈 문자열 반환.

        wait_selector 를 주면 해당 셀렉터가 렌더될 때까지 대기한다(동적 콘텐츠 대응).
        """
        if self.browser is None:
            raise RuntimeError("init_browser()를 먼저 호출하세요")

        attempts = retries if retries is not None else self.MAX_RETRIES
        for attempt in range(1, attempts + 1):
            page: Page = await self.browser.new_page(user_agent=self.ua.random)
            try:
                # SPA 대응: networkidle 은 백그라운드 요청(분석 스크립트 등)이 끊이지 않아
                # 타임아웃이 잦다 → domcontentloaded 로 빠르게 진입 후 핵심 셀렉터 렌더를 대기.
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=timeout)
                content = await page.content()
                await asyncio.sleep(random.uniform(1, 3))
                return content
            except Exception as e:
                if attempt < attempts:
                    logger.warning(f"fetch_page 재시도 {attempt}/{attempts}: {url} — {e}")
                    await asyncio.sleep(random.uniform(1, 3))
                else:
                    logger.error(f"fetch_page 실패 ({attempts}회 시도): {url} — {e}")
            finally:
                await page.close()
        return ""

    async def safe_select(self, page: Page, selector: str, default: str = "") -> str:
        """셀렉터 실패 시 default(빈 문자열) 반환"""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.inner_text()
            return default
        except Exception:
            return default

    async def save_to_db(self, data: list[dict]) -> None:
        """수집 데이터를 queries.upsert_lecture()로 저장 (DB 직접 접근 금지)"""
        for item in data:
            try:
                upsert_lecture(LectureCreate(**item))
            except Exception as e:
                logger.error(f"DB 저장 실패: {item.get('title')} — {e}")

    async def close(self) -> None:
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
