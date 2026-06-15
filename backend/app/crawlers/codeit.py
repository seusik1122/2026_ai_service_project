"""코드잇 크롤러 — IT/개발 강의."""
import re
import requests
from bs4 import BeautifulSoup
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

CATEGORY_KEYWORDS = {
    "python": "IT/개발",
    "javascript": "IT/개발",
    "java": "IT/개발",
    "web": "웹개발",
    "data": "데이터사이언스",
    "ai": "AI/머신러닝",
    "figma": "디자인",
    "kdc": "IT/개발",
    "computer": "IT/개발",
    "programming": "IT/개발",
    "productivity": "업무생산성",
}


class CodeitCrawler:
    PLATFORM = "codeit"

    async def crawl(self) -> list[dict]:
        collected: list[dict] = []
        urls = self._get_course_urls()
        logger.info(f"코드잇 URL 수집: {len(urls)}개")

        for url, category in urls:
            title = self._extract_title_from_url(url)
            if not title:
                continue
            try:
                upsert_lecture(LectureCreate(
                    platform=self.PLATFORM,
                    title=title,
                    instructor_name=None,
                    category=category,
                    price=None,
                    rating=None,
                    student_count=None,
                    url=url,
                    thumbnail_url=None,
                    tags=None,
                    is_free=False,
                ))
                collected.append({"url": url, "title": title})
            except Exception as e:
                logger.error(f"코드잇 DB 저장 실패: {e}")

        logger.info(f"코드잇 완료: {len(collected)}건")
        return collected

    def _get_course_urls(self) -> list[tuple[str, str]]:
        urls = []
        try:
            r = requests.get("https://www.codeit.kr/server-sitemap.xml", headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "xml")
            for loc in soup.find_all("loc"):
                url = loc.text.strip()
                if any(k in url for k in ["/paths/", "/kdc/courses/"]):
                    category = self._guess_category(url)
                    urls.append((url, category))
        except Exception as e:
            logger.error(f"코드잇 sitemap 수집 실패: {e}")
        return urls

    @staticmethod
    def _guess_category(url: str) -> str:
        lower = url.lower()
        for keyword, category in CATEGORY_KEYWORDS.items():
            if keyword in lower:
                return category
        return "IT/개발"

    @staticmethod
    def _extract_title_from_url(url: str) -> str:
        path = url.rstrip("/").split("/")[-1]
        # URL 디코딩 후 slug → 제목
        from urllib.parse import unquote
        decoded = unquote(path)
        # 하이픈/언더스코어 → 공백, 앞 숫자 제거
        title = re.sub(r"^[\d\-_]+", "", decoded.replace("-", " ").replace("_", " ")).strip()
        return title[:200] if len(title) >= 3 else ""
