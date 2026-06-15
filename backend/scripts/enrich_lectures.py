"""강의 정보 보강 스크립트.

파이프라인 (강의 1건당):
  1. 상세 페이지 크롤링 → 설명, 난이도, 커리큘럼
  2. 네이버 블로그 검색 → 강의명 후기
  3. 유튜브 검색 → 관련 영상 댓글
  4. 구글 검색 → 외부 블로그 후기
  5. GPT 종합 → tags 생성
  6. DB 업데이트

실행:
  cd /mnt/c/ai_service/backend
  python -m scripts.enrich_lectures              # 전체
  python -m scripts.enrich_lectures --platform inflearn
  python -m scripts.enrich_lectures --limit 100  # 테스트
  python -m scripts.enrich_lectures --platform inflearn --limit 10
"""
import argparse
import asyncio
import json
import os
import random
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import AsyncOpenAI
from playwright.async_api import async_playwright

load_dotenv()

from app.db.supabase_client import supabase
from app.db.queries import enrich_lecture
from app.utils.logger import logger

# ── 설정 ──────────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

BATCH_SIZE = 10       # GPT 호출 단위
CRAWL_DELAY = (1, 3)  # 크롤링 딜레이 (초)
MAX_TEXT_LEN = 800    # GPT 입력 소스별 최대 길이

GPT_MODEL = "gpt-4o-mini"

_GPT_SYSTEM = """\
너는 온라인 강의 분석 전문가야.
아래에 강의 기본 정보와 수집된 데이터(상세 페이지, 후기, 댓글 등)가 주어진다.
이를 종합해서 JSON으로만 응답해.

규칙:
1. level: "입문" | "초급" | "중급" | "고급" | "모든수준" 중 하나
2. description: 이 강의가 무엇을 가르치는지 2~3문장. 실제 데이터 기반으로 작성, 추측 최소화
3. curriculum: 강의의 주요 학습 내용/섹션을 배열로 (최대 6개, 없으면 빈 배열)
4. keywords: 이 강의를 대표하는 핵심 키워드 (최대 5개)
5. 수집된 데이터가 부족하면 제목과 카테고리에서 합리적으로 추론하되, 확실하지 않은 건 짧게

응답 형식 (JSON만, 마크다운 금지):
{
  "level": "초급",
  "description": "...",
  "curriculum": ["섹션1", "섹션2"],
  "keywords": ["키워드1", "키워드2"]
}
"""


# ── 1. 상세 페이지 크롤링 ─────────────────────────────────────────────────

async def _crawl_detail(page, url: str, platform: str) -> dict:
    """강의 상세 페이지에서 설명/난이도/커리큘럼 추출."""
    result = {"description": "", "level": "", "curriculum": []}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(random.randint(1500, 2500))
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # og:description (거의 모든 플랫폼 공통)
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc:
            result["description"] = og_desc.get("content", "")[:MAX_TEXT_LEN]

        # 플랫폼별 추가 파싱
        if platform == "inflearn":
            result.update(_parse_inflearn(soup, text))
        elif platform == "coloso":
            result.update(_parse_coloso(soup, text))
        elif platform == "class101":
            result.update(_parse_class101(soup, text))
        elif platform == "fastcampus":
            result.update(_parse_fastcampus(soup, text))
        else:
            result.update(_parse_generic(soup, text))

    except Exception as e:
        logger.warning(f"상세 페이지 크롤링 실패 ({url[:50]}): {e}")
    return result


def _parse_inflearn(soup: BeautifulSoup, text: str) -> dict:
    result = {}
    # 난이도
    level_m = re.search(r"(입문|초급|중급|고급|모든\s*수준)", text)
    if level_m:
        result["level"] = level_m.group(1).replace(" ", "")
    # 강의 소개 본문
    content_el = soup.select_one("[class*=content]") or soup.select_one("article")
    if content_el:
        desc = content_el.get_text(separator=" ", strip=True)[:MAX_TEXT_LEN]
        if len(desc) > 50:
            result["description"] = desc
    # 커리큘럼 섹션 제목
    curriculum = []
    for h in soup.find_all(["h2", "h3", "h4"]):
        t = h.get_text(strip=True)
        if t and len(t) > 2 and len(t) < 50 and "커리큘럼" not in t:
            curriculum.append(t)
    result["curriculum"] = curriculum[:6]
    # 수강생/평점 업데이트
    student_m = re.search(r"([\d,]+)\s*명", text)
    rating_m = re.search(r"(\d\.\d)\s*점", text)
    if student_m:
        result["student_count"] = int(student_m.group(1).replace(",", ""))
    if rating_m:
        result["rating"] = float(rating_m.group(1))
    return result


def _parse_coloso(soup: BeautifulSoup, text: str) -> dict:
    result = {}
    level_m = re.search(r"(입문|초급|중급|고급|베이직|어드밴스)", text)
    if level_m:
        result["level"] = level_m.group(1)
    # 가격 보정
    price_m = re.search(r"([\d,]+)\s*원", text)
    if price_m:
        result["price"] = int(price_m.group(1).replace(",", ""))
    headings = [h.get_text(strip=True) for h in soup.find_all(["h2", "h3"]) if 3 < len(h.get_text(strip=True)) < 50]
    result["curriculum"] = headings[:6]
    return result


def _parse_class101(soup: BeautifulSoup, text: str) -> dict:
    result = {}
    level_m = re.search(r"(입문|초급|중급|고급|누구나|처음)", text)
    if level_m:
        result["level"] = level_m.group(1)
    student_m = re.search(r"([\d,]+)\s*명", text)
    if student_m:
        result["student_count"] = int(student_m.group(1).replace(",", ""))
    rating_m = re.search(r"(\d\.\d)\s*(점|/\s*5)", text)
    if rating_m:
        result["rating"] = float(rating_m.group(1))
    return result


def _parse_fastcampus(soup: BeautifulSoup, text: str) -> dict:
    result = {}
    level_m = re.search(r"(입문|초급|중급|고급|기초|심화)", text)
    if level_m:
        result["level"] = level_m.group(1)
    instructor_el = soup.select_one("[class*=instructor]") or soup.select_one("[class*=teacher]")
    if instructor_el:
        name = instructor_el.get_text(strip=True)[:30]
        if name:
            result["instructor_name"] = name
    return result


def _parse_generic(soup: BeautifulSoup, text: str) -> dict:
    result = {}
    level_m = re.search(r"(입문|초급|중급|고급|기초|심화|누구나)", text)
    if level_m:
        result["level"] = level_m.group(1)
    return result


# ── 2. 네이버 블로그 후기 ────────────────────────────────────────────────

def _fetch_naver_reviews(title: str, platform: str) -> str:
    """네이버 블로그 API로 강의 후기 검색."""
    if not NAVER_CLIENT_ID:
        return ""
    query = f"{title} 수강후기"
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/blog.json",
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": query, "display": 5, "sort": "date"},
            timeout=8,
        )
        items = resp.json().get("items", [])
        snippets = []
        for item in items:
            raw = f"{item.get('title','')} {item.get('description','')}".strip()
            clean = re.sub(r"<[^>]+>", "", raw)
            if len(clean) > 30:
                snippets.append(clean[:200])
        return " | ".join(snippets)[:MAX_TEXT_LEN]
    except Exception as e:
        logger.warning(f"네이버 후기 실패 ({title[:20]}): {e}")
        return ""


# ── 3. 유튜브 댓글 ──────────────────────────────────────────────────────

def _fetch_youtube_comments(title: str) -> str:
    """유튜브 API로 강의 관련 영상 댓글 수집."""
    if not YOUTUBE_API_KEY:
        return ""
    try:
        # 영상 검색
        search_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": YOUTUBE_API_KEY,
                "part": "snippet",
                "q": f"{title} 후기 리뷰",
                "maxResults": 3,
                "type": "video",
                "relevanceLanguage": "ko",
            },
            timeout=8,
        )
        videos = search_resp.json().get("items", [])
        if not videos:
            return ""

        # 첫 번째 영상 댓글
        video_id = videos[0]["id"]["videoId"]
        comments_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/commentThreads",
            params={
                "key": YOUTUBE_API_KEY,
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 20,
                "order": "relevance",
            },
            timeout=8,
        )
        items = comments_resp.json().get("items", [])
        comments = []
        for item in items:
            text = item["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "")
            clean = re.sub(r"<[^>]+>", "", text).strip()
            if len(clean) > 20:
                comments.append(clean[:150])
        return " | ".join(comments[:10])[:MAX_TEXT_LEN]
    except Exception as e:
        logger.warning(f"유튜브 댓글 실패 ({title[:20]}): {e}")
        return ""


def _fetch_youtube_comments_by_url(url: str) -> str:
    """유튜브 강의 URL에서 직접 댓글 수집."""
    if not YOUTUBE_API_KEY:
        return ""
    try:
        m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        if not m:
            return ""
        video_id = m.group(1)
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/commentThreads",
            params={
                "key": YOUTUBE_API_KEY,
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 30,
                "order": "relevance",
            },
            timeout=8,
        )
        items = resp.json().get("items", [])
        comments = []
        for item in items:
            text = item["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "")
            clean = re.sub(r"<[^>]+>", "", text).strip()
            if len(clean) > 20:
                comments.append(clean[:150])
        return " | ".join(comments[:15])[:MAX_TEXT_LEN]
    except Exception as e:
        logger.warning(f"유튜브 댓글 직접 수집 실패 ({url[:40]}): {e}")
        return ""


# ── 4. 구글 검색 후기 ────────────────────────────────────────────────────

async def _fetch_google_reviews(page, title: str) -> str:
    """구글 검색으로 외부 블로그 후기 수집."""
    try:
        query = f"{title} 수강후기 솔직"
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=5"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(random.randint(1000, 2000))
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        snippets = []
        for el in soup.select("div.VwiC3b, div.s3v9rd, span.aCOpRe, div[data-sncf]"):
            t = el.get_text(separator=" ", strip=True)
            if len(t) > 40:
                snippets.append(t[:200])
        return " | ".join(snippets[:5])[:MAX_TEXT_LEN]
    except Exception as e:
        logger.warning(f"구글 후기 실패 ({title[:20]}): {e}")
        return ""


# ── 5. GPT 종합 → tags 생성 ──────────────────────────────────────────────

async def _gpt_enrich(
    client: AsyncOpenAI,
    lecture: dict,
    detail: dict,
    naver_text: str,
    youtube_text: str,
    google_text: str,
) -> dict:
    """수집된 모든 소스를 GPT에 넣어 tags 생성."""
    sources = []
    if detail.get("description"):
        sources.append(f"[상세페이지] {detail['description'][:400]}")
    if naver_text:
        sources.append(f"[네이버후기] {naver_text[:300]}")
    if youtube_text:
        sources.append(f"[유튜브댓글] {youtube_text[:300]}")
    if google_text:
        sources.append(f"[구글후기] {google_text[:300]}")
    if detail.get("curriculum"):
        sources.append(f"[커리큘럼] {' / '.join(detail['curriculum'])}")

    user_content = (
        f"강의 제목: {lecture['title']}\n"
        f"플랫폼: {lecture['platform']}\n"
        f"카테고리: {lecture.get('category') or '미분류'}\n"
        f"강사: {lecture.get('instructor_name') or '미상'}\n\n"
        f"수집 데이터:\n" + "\n".join(sources) if sources else "수집 데이터 없음"
    )

    try:
        resp = await client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": _GPT_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=400,
        )
        result = json.loads(resp.choices[0].message.content)
        return result
    except Exception as e:
        logger.error(f"GPT 보강 실패 ({lecture['title'][:20]}): {e}")
        return {}


def _build_tags(gpt: dict, detail: dict) -> list[str]:
    """GPT 결과 + 크롤링 결과를 tags 배열로 변환."""
    tags = []

    level = gpt.get("level") or detail.get("level")
    if level:
        tags.append(f"level:{level}")

    desc = gpt.get("description")
    if desc:
        tags.append(f"desc:{desc[:300]}")

    curriculum = gpt.get("curriculum") or detail.get("curriculum") or []
    if curriculum:
        joined = "|".join(str(c) for c in curriculum[:6])
        tags.append(f"curriculum:{joined}")

    for kw in (gpt.get("keywords") or [])[:5]:
        tags.append(f"keyword:{kw}")

    return tags


# ── 메인 파이프라인 ───────────────────────────────────────────────────────

def _needs_enrich(lecture: dict) -> bool:
    """desc: 태그가 없는 강의만 대상."""
    tags = lecture.get("tags") or []
    return not any(t.startswith("desc:") for t in tags)


def _fetch_target_lectures(platform_filter: Optional[str], limit: Optional[int]) -> list[dict]:
    """보강 대상 강의 조회 — tags null이거나 desc: 없는 강의 (youtube 포함)."""
    all_rows = []
    offset = 0
    page_size = 1000
    while True:
        q = (
            supabase.table("lectures")
            .select("id,platform,title,url,category,instructor_name,tags,rating,student_count")
        )
        if platform_filter:
            q = q.eq("platform", platform_filter)
        rows = q.range(offset, offset + page_size - 1).execute().data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    targets = [r for r in all_rows if _needs_enrich(r)]
    if limit:
        targets = targets[:limit]
    return targets


async def enrich_all(platform_filter: Optional[str] = None, limit: Optional[int] = None):
    targets = _fetch_target_lectures(platform_filter, limit)
    total = len(targets)
    logger.info(f"보강 대상: {total}건 (platform={platform_filter or '전체'})")

    if limit:
        total = min(total, limit)

    logger.info(f"보강 대상: {total}건 (platform={platform_filter or '전체'})")

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    done = 0
    skipped = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        detail_page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        google_page = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36"
        )

        try:
            for lecture in targets:
                lec_title = lecture["title"][:40]
                is_youtube = lecture["platform"] == "youtube"
                logger.info(f"[{done+1}/{total}] {lecture['platform']} | {lec_title}")

                # 1. 상세 페이지 크롤링 (유튜브는 건너뜀)
                detail = {}
                if not is_youtube and lecture.get("url"):
                    detail = await _crawl_detail(detail_page, lecture["url"], lecture["platform"])
                    await asyncio.sleep(random.uniform(*CRAWL_DELAY))

                # 2. 네이버 후기
                naver_text = await asyncio.to_thread(_fetch_naver_reviews, lecture["title"], lecture["platform"])

                # 3. 유튜브 댓글
                # - 유튜브 강의: 해당 영상의 댓글 직접 수집
                # - 일반 강의: 강의명으로 후기 영상 검색 후 댓글 수집
                if is_youtube and lecture.get("url"):
                    youtube_text = await asyncio.to_thread(_fetch_youtube_comments_by_url, lecture["url"])
                else:
                    youtube_text = await asyncio.to_thread(_fetch_youtube_comments, lecture["title"])

                # 4. 구글 후기
                google_text = await _fetch_google_reviews(google_page, lecture["title"])
                await asyncio.sleep(random.uniform(1, 2))

                # 5. GPT 종합
                gpt_result = await _gpt_enrich(client, lecture, detail, naver_text, youtube_text, google_text)

                # 6. DB 업데이트 — 기존 tags 유지하면서 desc:/level:/keyword: 만 갱신
                new_tags = _build_tags(gpt_result, detail)
                if not new_tags:
                    skipped += 1
                    logger.warning(f"  tags 생성 실패, 스킵: {lec_title}")
                    done += 1
                    continue

                existing = [t for t in (lecture.get("tags") or [])
                            if not any(t.startswith(p) for p in ("level:", "desc:", "curriculum:", "keyword:"))]
                merged_tags = existing + new_tags

                update_fields = {"tags": merged_tags}
                if detail.get("rating") and not lecture.get("rating"):
                    update_fields["rating"] = detail["rating"]
                if detail.get("student_count") and not lecture.get("student_count"):
                    update_fields["student_count"] = detail["student_count"]
                if detail.get("instructor_name") and not lecture.get("instructor_name"):
                    update_fields["instructor_name"] = detail["instructor_name"]
                if detail.get("price") is not None and lecture.get("price") in (None, 0):
                    update_fields["price"] = detail["price"]

                enrich_lecture(lecture["id"], update_fields)
                done += 1
                logger.info(f"  완료: tags={len(merged_tags)}개 | {new_tags[:2]}")

        finally:
            await browser.close()

    logger.info(f"보강 완료: {done}건 처리, {skipped}건 스킵")
    await _notify_done(done, skipped, total)


async def _notify_done(done: int, skipped: int, total: int) -> None:
    """완료 시 Zapier 웹훅으로 이메일 발송."""
    webhook_url = os.getenv("ZAPIER_DDAY_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("ZAPIER_DDAY_WEBHOOK_URL 미설정 — 완료 알림 스킵")
        return
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={
                "to": os.getenv("ADMIN_EMAIL", "kkhlhj485@gmail.com"),
                "subject": f"[강의 보강 완료] {done}/{total}건 처리됨",
                "body": (
                    f"강의 정보 보강 스크립트가 완료되었습니다.\n\n"
                    f"처리: {done}건\n"
                    f"스킵: {skipped}건\n"
                    f"전체 대상: {total}건"
                ),
            }, timeout=10)
        logger.info("완료 알림 이메일 발송")
    except Exception as e:
        logger.error(f"완료 알림 발송 실패: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="강의 정보 보강 스크립트")
    parser.add_argument("--platform", type=str, default=None, help="특정 플랫폼만 처리 (예: inflearn)")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 건수")
    args = parser.parse_args()

    asyncio.run(enrich_all(platform_filter=args.platform, limit=args.limit))
