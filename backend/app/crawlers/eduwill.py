"""에듀윌 크롤러 — 공무원/자격증/IT."""
import asyncio
import random
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger

# grh.eduwill.net: 국비지원 IT/자격증 강의 (실제 강의 링크가 있는 서브도메인)
# www.eduwill.net: 공무원/공인중개사 등 본 사이트
CATEGORIES = [
    # grh 서브도메인 (국비지원)
    ("IT/개발",        "https://grh.eduwill.net/front/lecture/?cs=6"),
    ("영상/디자인",    "https://grh.eduwill.net/front/lecture/?cs=2"),
    ("전기/안전",      "https://grh.eduwill.net/front/lecture/?cs=1"),
    ("세무/회계",      "https://grh.eduwill.net/front/lecture/?cs=3"),
    # 본 사이트
    ("공무원",         "https://www.eduwill.net/gosi"),
    ("공인중개사",     "https://www.eduwill.net/realEstate"),
    ("사회복지사",     "https://www.eduwill.net/welfare"),
]


class EduwillCrawler:
    PLATFORM = "eduwill"

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )
            page = await ctx.new_page()
            await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

            try:
                for cat_name, url in CATEGORIES:
                    logger.info(f"에듀윌 크롤링: {cat_name}")
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(5000)

                        for _ in range(3):
                            await page.keyboard.press("End")
                            await page.wait_for_timeout(1000)

                        items = await self._parse_page(page, cat_name, url)
                        for item in items:
                            try:
                                if item.get("instructor_name"):
                                    upsert_instructor(item["instructor_name"], self.PLATFORM)
                                upsert_lecture(LectureCreate(**item))
                                collected.append(item)
                            except Exception as e:
                                logger.error(f"에듀윌 DB 저장 실패: {e}")

                        logger.info(f"  {cat_name}: {len(items)}건")
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    except Exception as e:
                        logger.error(f"에듀윌 {cat_name} 실패: {e}")
            finally:
                await browser.close()

        logger.info(f"에듀윌 완료: {len(collected)}건")
        return collected

    async def _parse_page(self, page, category: str, base_url: str) -> list[dict]:
        links = await page.eval_on_selector_all(
            'a[href]',
            'els => [...new Map(els.map(e => [e.href.split("?")[0], {href: e.href, text: e.innerText.trim()}])).values()]'
        )
        items = []
        seen = set()
        for link in links:
            href = link["href"]
            text = link["text"].strip()
            if not text or href in seen or len(text) < 3:
                continue
            if not any(d in href for d in ["eduwill.net"]):
                continue
            if any(k in href for k in ["javascript", "login", "main", "event", "counsel", "notice", "faq", "mypage"]):
                continue
            # 강의 상세/목록 패턴
            if not any(k in href for k in ["li=", "lecture", "lec", "course", "detail", "product", "gosi", "realEstate", "welfare", "accounting"]):
                continue
            if len(text) > 100:
                continue
            seen.add(href)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else text[:100]
            if not title or len(title) < 3:
                continue

            # 절대 URL 보정
            if href.startswith("/"):
                domain = "/".join(base_url.split("/")[:3])
                href = domain + href

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
        m = re.search(r"([가-힣]{2,4})\s*(선생님|쌤|강사|교수)", text)
        return m.group(1) if m else None

    @staticmethod
    def _extract_price(text: str) -> tuple[Optional[int], bool]:
        if "무료" in text or "국비" in text:
            return 0, True
        m = re.search(r"([\d,]+)\s*원", text)
        if m:
            digits = m.group(1).replace(",", "")
            return (int(digits), False) if digits else (None, False)
        return None, False
