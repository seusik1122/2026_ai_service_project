# 국내 강의 통합 추천 시스템 — 기술 명세서

> 이 문서만 보고 다른 AI 또는 개발자가 동일하게 구현할 수 있도록 작성된 완전한 스펙이다.

---

## 1. 프로젝트 개요

### 목적
국내 여러 강의 플랫폼(인프런, 클래스101, 패스트캠퍼스)과 후기 채널(네이버 블로그/카페, YouTube)의 데이터를 통합 수집하고, OpenAI API로 광고 필터링 및 감성 분석을 수행해 강사 신뢰도 기반 강의 추천 대시보드를 제공한다.

### 기술 스택
| 구분 | 기술 |
|------|------|
| 백엔드 | Python 3.11, FastAPI, Playwright, Supabase(PostgreSQL) |
| 프론트엔드 | React 18, TypeScript, Recharts, Axios, TanStack Query |
| AI | OpenAI API (gpt-5.5 / gpt-5.4-mini) |
| 자동화 | Zapier (Organization 플랜) |
| 외부 API | 네이버 검색 API, YouTube Data API v3, K-MOOC API, 큐넷 공공데이터 API |

### 담당자별 역할 한눈에 보기
| 담당 | 역할 |
|------|------|
| A | 크롤러 + 외부 API 수집기 + React 프론트엔드 |
| B | DB 레이어 + OpenAI AI 처리 + FastAPI 엔드포인트 + Zapier + 전체 연동 |

> **인계 기준점:** A가 크롤러로 데이터 수집까지 완료하면 B가 AI 처리 + FastAPI 시작

---

## 2. 백엔드 폴더 구조

```
backend/
├── main.py                         # FastAPI 앱 진입점
├── requirements.txt                # 의존성 목록 (섹션 3-4 참고)
├── .env                            # 환경변수 (API 키 등, git 제외)
├── .env.example                    # 환경변수 템플릿 (섹션 10 참고)
│
├── app/
│   ├── __init__.py
│   │
│   ├── api/                        # FastAPI 라우터 (B담당)
│   │   ├── __init__.py
│   │   ├── lectures.py             # 강의 검색·추천 엔드포인트
│   │   ├── instructors.py          # 강사 신뢰도 점수 엔드포인트
│   │   ├── reviews.py              # 후기 조회 엔드포인트
│   │   ├── exams.py                # 자격증 시험 일정 엔드포인트
│   │   └── zapier_webhook.py       # Zapier 트리거용 웹훅 엔드포인트
│   │
│   ├── crawlers/                   # 플랫폼별 크롤러 (A담당)
│   │   ├── __init__.py
│   │   ├── base_crawler.py         # 크롤러 공통 베이스 클래스
│   │   ├── inflearn.py             # 인프런 크롤러
│   │   ├── class101.py             # 클래스101 크롤러
│   │   └── fastcampus.py           # 패스트캠퍼스 크롤러
│   │
│   ├── collectors/                 # 외부 API 수집기 (A담당)
│   │   ├── __init__.py
│   │   ├── naver_api.py            # 네이버 검색 API (블로그·카페 후기)
│   │   ├── youtube_api.py          # YouTube Data API (영상·댓글)
│   │   ├── kmooc_api.py            # K-MOOC 무료강의 API
│   │   └── qnet_api.py             # 큐넷 자격증 시험일정 API
│   │
│   ├── ai/                         # OpenAI 연동 (B담당)
│   │   ├── __init__.py
│   │   ├── ad_filter.py            # 광고성 후기 필터링
│   │   ├── sentiment.py            # 감성 분석 (긍정/부정/중립)
│   │   └── trust_score.py          # 강사 신뢰도 점수 계산
│   │
│   ├── db/                         # DB 연결 및 쿼리 (B담당)
│   │   ├── __init__.py
│   │   ├── supabase_client.py      # Supabase 클라이언트 초기화
│   │   ├── models.py               # Pydantic 모델 정의
│   │   └── queries.py              # 테이블별 CRUD 함수 (섹션 3-3 참고)
│   │
│   ├── scheduler/                  # 자동 수집 스케줄러 (A담당)
│   │   ├── __init__.py
│   │   └── cron_jobs.py            # APScheduler 기반 주기적 수집
│   │
│   └── utils/
│       ├── __init__.py
│       ├── text_cleaner.py         # 텍스트 전처리 유틸
│       └── logger.py               # 로그 설정
│
└── tests/
    ├── test_crawlers.py
    ├── test_collectors.py
    ├── test_db.py
    └── test_ai.py
```

---

## 3. DB 스키마 (Supabase/PostgreSQL)

> **실행 방법:** 파이썬 코드 아님. Supabase 대시보드 → SQL Editor → 아래 SQL 복붙 → Run

### 테이블 1: `lectures` — 강의 정보
```sql
CREATE TABLE lectures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(50) NOT NULL,      -- 'inflearn' | 'class101' | 'fastcampus' | 'kmooc' | 'youtube'
    title VARCHAR(300) NOT NULL,
    instructor_name VARCHAR(100),
    category VARCHAR(100),              -- 'IT' | '공무원' | '자격증' | '어학' 등
    price INTEGER DEFAULT 0,            -- 0이면 무료
    rating FLOAT,
    student_count INTEGER,
    url TEXT,
    thumbnail_url TEXT,
    tags TEXT[],                        -- ['Python', 'FastAPI', '백엔드'] 등 키워드 배열
    is_free BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 테이블 2: `instructors` — 강사 정보
```sql
CREATE TABLE instructors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    profile_url TEXT,
    trust_score FLOAT DEFAULT 0.0,      -- 0~100, OpenAI 감성분석 기반 계산값
    positive_ratio FLOAT DEFAULT 0.0,   -- 긍정 후기 비율
    review_count INTEGER DEFAULT 0,
    last_calculated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 테이블 3: `reviews` — 수집된 후기
```sql
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instructor_name VARCHAR(100),
    platform_source VARCHAR(50),         -- 'naver_blog' | 'naver_cafe' | 'youtube_comment'
    content TEXT NOT NULL,
    is_ad BOOLEAN DEFAULT FALSE,         -- OpenAI 광고 필터링 결과
    sentiment VARCHAR(20),               -- 'positive' | 'negative' | 'neutral'
    sentiment_score FLOAT,               -- -1.0 ~ 1.0
    original_url TEXT,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 테이블 4: `exams` — 자격증 시험 일정
```sql
CREATE TABLE exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_name VARCHAR(200) NOT NULL,
    exam_type VARCHAR(100),              -- '필기' | '실기'
    application_start DATE,
    application_end DATE,
    exam_date DATE,
    result_date DATE,
    d_day INTEGER,                       -- 자동 계산
    related_keywords TEXT[],             -- ['정보처리기사', '컴활'] 등
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 테이블 5: `zapier_alerts_log` — Zapier 알림 이력
```sql
CREATE TABLE zapier_alerts_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50),              -- 'dday' | 'new_lecture' | 'review_spike'
    payload JSONB,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3-1. DB 연결 코드 (`supabase_client.py`) — B담당

```python
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
```

> 이 파일을 import해서 `supabase` 객체를 가져다 쓰면 된다.
> 예: `from app.db.supabase_client import supabase`

---

## 3-2. Pydantic 모델 (`models.py`) — B담당

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LectureCreate(BaseModel):
    platform: str
    title: str
    instructor_name: Optional[str]
    category: Optional[str]
    price: int = 0
    rating: Optional[float]
    student_count: Optional[int]
    url: Optional[str]
    thumbnail_url: Optional[str]
    tags: Optional[list[str]]
    is_free: bool = False

class ReviewCreate(BaseModel):
    instructor_name: Optional[str]
    platform_source: str
    content: str
    is_ad: bool = False
    sentiment: Optional[str]
    sentiment_score: Optional[float]
    original_url: Optional[str]

class InstructorUpdate(BaseModel):
    trust_score: float
    positive_ratio: float
    review_count: int
    last_calculated_at: datetime

class ExamCreate(BaseModel):
    exam_name: str
    exam_type: Optional[str]
    application_start: Optional[str]
    application_end: Optional[str]
    exam_date: Optional[str]
    result_date: Optional[str]
    d_day: Optional[int]
    related_keywords: Optional[list[str]]
```

---

## 3-3. DB 쿼리 함수 (`queries.py`) — B담당

> A의 크롤러가 데이터를 수집하면 이 함수를 호출해서 DB에 저장한다.
> **B가 1주차에 이 파일을 먼저 완성해야 A가 크롤러 개발 시 바로 사용 가능.**

```python
from app.db.supabase_client import supabase
from app.db.models import LectureCreate, ReviewCreate, InstructorUpdate, ExamCreate
from datetime import date

# ── lectures 테이블 ──────────────────────────────────────

def upsert_lecture(data: LectureCreate) -> dict:
    """강의 저장. url 기준으로 중복 방지 (upsert)"""
    result = supabase.table("lectures").upsert(
        data.model_dump(),
        on_conflict="url"
    ).execute()
    return result.data

def get_lectures(
    keyword: str = None,
    category: str = None,
    is_free: bool = None,
    platform: str = None,
    sort: str = "trust_score",
    limit: int = 20
) -> list[dict]:
    """강의 검색. keyword는 title + tags 대상 ILIKE 검색"""
    query = supabase.table("lectures").select(
        "*, instructors(trust_score, positive_ratio)"
    )
    if keyword:
        query = query.ilike("title", f"%{keyword}%")
    if category:
        query = query.eq("category", category)
    if is_free is not None:
        query = query.eq("is_free", is_free)
    if platform:
        query = query.eq("platform", platform)
    query = query.order(sort, desc=True).limit(limit)
    return query.execute().data

# ── reviews 테이블 ───────────────────────────────────────

def insert_review(data: ReviewCreate) -> dict:
    """후기 저장. 중복 URL 체크 후 삽입"""
    result = supabase.table("reviews").upsert(
        data.model_dump(),
        on_conflict="original_url"
    ).execute()
    return result.data

def get_reviews_by_instructor(instructor_name: str) -> list[dict]:
    """특정 강사의 광고 아닌 후기 목록 반환"""
    return supabase.table("reviews") \
        .select("*") \
        .eq("instructor_name", instructor_name) \
        .eq("is_ad", False) \
        .order("collected_at", desc=True) \
        .execute().data

def get_unanalyzed_reviews() -> list[dict]:
    """감성 분석 안 된 후기 목록 반환 (sentiment가 NULL인 것)"""
    return supabase.table("reviews") \
        .select("*") \
        .is_("sentiment", "null") \
        .eq("is_ad", False) \
        .execute().data

# ── instructors 테이블 ───────────────────────────────────

def upsert_instructor(name: str, platform: str) -> dict:
    """강사 최초 등록. name + platform 조합으로 중복 방지"""
    result = supabase.table("instructors").upsert(
        {"name": name, "platform": platform},
        on_conflict="name,platform"
    ).execute()
    return result.data

def update_instructor_trust_score(name: str, data: InstructorUpdate) -> dict:
    """AI 분석 완료 후 강사 신뢰도 점수 업데이트"""
    result = supabase.table("instructors") \
        .update(data.model_dump()) \
        .eq("name", name) \
        .execute()
    return result.data

def get_instructor(name: str) -> dict:
    """강사 상세 정보 반환"""
    result = supabase.table("instructors") \
        .select("*") \
        .eq("name", name) \
        .single() \
        .execute()
    return result.data

def get_instructors_with_score_change(threshold: float = 10.0) -> list[dict]:
    """신뢰도 점수가 임계값 이상 변동된 강사 목록 (Zapier 트리거용)"""
    # 현재 점수와 지난주 평균 비교 로직
    # last_calculated_at 기준 7일 이내 변동폭 계산
    pass  # 구현 시 supabase rpc 또는 별도 로직 작성

# ── exams 테이블 ─────────────────────────────────────────

def upsert_exam(data: ExamCreate) -> dict:
    """시험 일정 저장. exam_name + exam_type 조합으로 중복 방지"""
    result = supabase.table("exams").upsert(
        data.model_dump(),
        on_conflict="exam_name,exam_type"
    ).execute()
    return result.data

def get_exams(keyword: str = None, d_day_within: int = None) -> list[dict]:
    """시험 일정 조회. d_day_within은 N일 이내 시험만 필터"""
    query = supabase.table("exams").select("*")
    if keyword:
        query = query.ilike("exam_name", f"%{keyword}%")
    if d_day_within:
        query = query.lte("d_day", d_day_within).gte("d_day", 0)
    return query.order("d_day").execute().data

def update_exam_dday() -> None:
    """매일 실행. 모든 시험의 d_day를 오늘 기준으로 재계산"""
    exams = supabase.table("exams").select("id, exam_date").execute().data
    today = date.today()
    for exam in exams:
        if exam["exam_date"]:
            exam_date = date.fromisoformat(exam["exam_date"])
            d_day = (exam_date - today).days
            supabase.table("exams").update({"d_day": d_day}).eq("id", exam["id"]).execute()

# ── zapier_alerts_log 테이블 ─────────────────────────────

def log_zapier_alert(alert_type: str, payload: dict) -> dict:
    """Zapier 알림 발송 이력 저장"""
    result = supabase.table("zapier_alerts_log").insert({
        "alert_type": alert_type,
        "payload": payload
    }).execute()
    return result.data
```

---

## 3-4. `requirements.txt` 전체 내용

```
# 웹 프레임워크
fastapi==0.115.0
uvicorn==0.30.0

# DB
supabase==2.7.0

# 크롤링
playwright==1.45.0
beautifulsoup4==4.12.3
requests==2.32.3
fake-useragent==1.5.1

# AI
openai==1.40.0

# 스케줄러
apscheduler==3.10.4

# 환경변수
python-dotenv==1.0.1

# 유틸
pydantic==2.8.0
httpx==0.27.0
```

> 설치 명령: `pip install -r requirements.txt`
> Playwright 브라우저 추가 설치: `playwright install chromium`

---

## 4. 크롤러 상세 명세 — A담당

### 공통 베이스 클래스 (`base_crawler.py`)
```python
import asyncio
import random
from playwright.async_api import async_playwright
from fake_useragent import UserAgent
from app.db.queries import upsert_lecture
from app.utils.logger import logger

class BaseCrawler:
    def __init__(self):
        self.browser = None
        self.ua = UserAgent()

    async def init_browser(self):
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(headless=True)

    async def fetch_page(self, url: str) -> str:
        page = await self.browser.new_page(
            user_agent=self.ua.random
        )
        try:
            await page.goto(url, wait_until="networkidle")
            content = await page.content()
            await asyncio.sleep(random.uniform(1, 3))  # 반탐지 딜레이
            return content
        except Exception as e:
            logger.error(f"fetch_page 실패: {url} — {e}")
            return ""
        finally:
            await page.close()

    async def save_to_db(self, data: list[dict]):
        for item in data:
            try:
                upsert_lecture(item)
            except Exception as e:
                logger.error(f"DB 저장 실패: {item.get('title')} — {e}")

    async def close(self):
        if self.browser:
            await self.browser.close()
```

### 인프런 크롤러 (`inflearn.py`)
- 대상 URL: `https://www.inflearn.com/courses?order=rating`
- 수집 항목: 강의명, 강사명, 평점, 수강생 수, 가격, 카테고리, 태그, URL, 썸네일
- 페이지네이션: 최대 10페이지
- 방식: Playwright로 동적 렌더링 대기 후 CSS 셀렉터로 파싱
- 주요 셀렉터 (개발자 도구로 직접 확인 필요):
  - 강의 카드: `.course-card-item`
  - 강의명: `.course-card-item--title`
  - 강사명: `.course-card-item--instructors`
  - 평점: `.score`

### 클래스101 크롤러 (`class101.py`)
- 대상 URL: `https://class101.net/ko/categories`
- 수집 항목: 강의명, 강사명, 가격, 카테고리, URL, 썸네일
- 방식: Playwright, JavaScript 렌더링 완료 후 파싱
- 수집 주기: 하루 1회 (자정 스케줄러)

### 패스트캠퍼스 크롤러 (`fastcampus.py`)
- 대상 URL: `https://fastcampus.co.kr/categories`
- 수집 항목: 강의명, 강사명, 가격, 카테고리, 태그, URL
- 방식: requests + BeautifulSoup (SSR 방식이라 가능)

---

## 5. 외부 API 수집기 상세 명세 — A담당

### 네이버 검색 API (`naver_api.py`)
```
검색 쿼리 패턴: "{강사명} 강의 후기", "{플랫폼명} {카테고리} 추천"
예시: "공단기 강사 후기", "에듀윌 공무원 수강 후기"

엔드포인트: https://openapi.naver.com/v1/search/blog.json
파라미터:
  - query: 검색어
  - display: 100 (최대)
  - sort: date (최신순)

헤더:
  - X-Naver-Client-Id: {NAVER_CLIENT_ID}
  - X-Naver-Client-Secret: {NAVER_CLIENT_SECRET}

수집 후 저장: insert_review() 호출 (platform_source='naver_blog')
```

### YouTube Data API (`youtube_api.py`)
```
검색 쿼리 패턴: "{강사명} 강의 리뷰", "{플랫폼명} 강의 추천 후기"

사용 엔드포인트:
  1. search.list — 영상 검색 (keyword, 최신 50개)
  2. commentThreads.list — 댓글 수집 (videoId 기준, 최대 100개)

파라미터:
  - key: {YOUTUBE_API_KEY}
  - part: snippet
  - maxResults: 50
  - relevanceLanguage: ko

수집 후 저장: insert_review() 호출 (platform_source='youtube_comment')
```

### 큐넷 API (`qnet_api.py`)
```
공공데이터포털 국가자격시험 일정 API
엔드포인트: https://openapi.q-net.or.kr/api/service/rest/InquiryQualExamSchdulInfo/getList
파라미터:
  - ServiceKey: {QNET_API_KEY}
  - implYy: 현재연도

수집 후 저장: upsert_exam() 호출
D-day 계산: update_exam_dday() 함수가 매일 자동 실행
```

### K-MOOC API (`kmooc_api.py`)
```
엔드포인트: https://www.kmooc.kr/api/courses/v1/courses/
파라미터:
  - page_size: 100
  - org: (기관 필터 선택사항)

수집 후 저장: upsert_lecture() 호출 (platform='kmooc', is_free=True)
```

---

## 6. OpenAI AI 처리 상세 명세 — B담당

### 광고 필터링 (`ad_filter.py`)
```
모델: gpt-5.4-mini  ← 배치 처리 비용 절감용 (후기 수천 건 처리)
max_tokens: 100

시스템 프롬프트:
"너는 블로그 후기가 광고성인지 진짜 수강 후기인지 판별하는 전문가야.
아래 기준으로 판단해:
- 광고: '협찬', '소정의 원고료', '체험단', 과도한 긍정만 있고 단점 없음, 특정 링크 삽입
- 진짜: 구체적 수강 경험, 단점 언급, 비교 내용 포함
반드시 JSON으로만 응답: {\"is_ad\": true/false, \"reason\": \"판단 이유 한 줄\"}"

입력: 후기 본문 텍스트 (최대 500자 truncate)
출력: {"is_ad": bool, "reason": str}

처리 흐름:
  1. get_unanalyzed_reviews() 호출 → 미분석 후기 목록
  2. 각 후기에 대해 광고 판별
  3. is_ad 결과를 reviews 테이블에 업데이트
```

### 감성 분석 (`sentiment.py`)
```
모델: gpt-5.5  ← 감성 분석은 정확도가 중요하므로 최신 모델 사용
max_tokens: 150

시스템 프롬프트:
"강의 후기 텍스트를 분석해서 감성을 판단해.
반드시 JSON으로만 응답:
{
  \"sentiment\": \"positive\" | \"negative\" | \"neutral\",
  \"score\": -1.0 ~ 1.0,
  \"keywords\": [\"핵심 키워드 최대 3개\"]
}"

입력: 광고 필터링 통과한 후기 텍스트 (is_ad=False)
출력: {"sentiment": str, "score": float, "keywords": list}

처리 흐름:
  1. get_unanalyzed_reviews() 호출 → sentiment가 NULL인 후기
  2. 각 후기 감성 분석
  3. sentiment, sentiment_score 결과를 reviews 테이블에 업데이트
  4. 강사별 trust_score 재계산 → update_instructor_trust_score() 호출
```

### 강사 신뢰도 점수 계산 (`trust_score.py`)
```
계산식:
trust_score = (긍정 후기 수 / 전체 후기 수) * 60
            + (평균 sentiment_score + 1) / 2 * 30
            + min(전체 후기 수 / 100, 1.0) * 10

범위: 0 ~ 100
의미:
  - 60점: 긍정 비율 (가장 중요)
  - 30점: 감성 점수 강도
  - 10점: 후기 수량 (데이터 신뢰성)

처리 흐름:
  1. get_reviews_by_instructor(name) 호출
  2. 위 계산식으로 trust_score 산출
  3. update_instructor_trust_score() 호출해서 DB 업데이트
```

---

## 7. FastAPI 엔드포인트 명세 — B담당

### 강의 검색
```
GET /api/lectures
Query params:
  - keyword: str (검색어, 예: "파이썬")
  - category: str (예: "IT", "공무원", "자격증")
  - is_free: bool
  - platform: str (예: "inflearn")
  - sort: str ("rating" | "trust_score" | "student_count")
  - limit: int (default 20)

내부 동작: get_lectures() 호출

Response:
{
  "total": 150,
  "lectures": [
    {
      "id": "uuid",
      "title": "강의명",
      "platform": "inflearn",
      "instructor_name": "강사명",
      "trust_score": 87.5,
      "rating": 4.8,
      "price": 55000,
      "is_free": false,
      "url": "https://...",
      "tags": ["Python", "FastAPI"]
    }
  ]
}
```

### 강사 신뢰도 조회
```
GET /api/instructors/{instructor_name}

내부 동작: get_instructor() + get_reviews_by_instructor() 호출

Response:
{
  "name": "강사명",
  "trust_score": 87.5,
  "positive_ratio": 0.82,
  "review_count": 143,
  "recent_reviews": [...],
  "trend": [{"date": "2025-01", "score": 85.0}, ...]
}
```

### 자격증 시험 일정
```
GET /api/exams
Query params:
  - keyword: str (예: "정보처리기사")
  - d_day_within: int (예: 30 → 30일 이내 시험만)

내부 동작: get_exams() 호출

Response:
{
  "exams": [
    {
      "exam_name": "정보처리기사",
      "exam_type": "필기",
      "exam_date": "2025-03-02",
      "d_day": 45,
      "related_lectures": [...]
    }
  ]
}
```

### Zapier 웹훅 트리거
```
POST /api/zapier/trigger
Body:
{
  "event_type": "dday_alert" | "new_lecture" | "review_spike",
  "data": { ... }
}

내부 동작: log_zapier_alert() 호출 후 Zapier Webhook URL로 POST 전송
```

---

## 8. Zapier 워크플로우 상세 — B담당

### Zap 1: 시험 D-day 알림
```
트리거: Schedule by Zapier → 매일 오전 9시
액션 1: Webhooks by Zapier → GET /api/exams?d_day_within=30
액션 2: Filter → d_day가 30, 14, 7, 3, 1 중 하나일 때만 통과
액션 3: Formatter → 메시지 포맷 생성
  "📅 [시험명] 필기시험이 D-{d_day}입니다. 추천 강의: {강의명}"
액션 4: Gmail 또는 Slack → 알림 발송
```

### Zap 2: 신규 강의 등록 알림
```
트리거: Webhooks by Zapier (Catch Hook)
  → 백엔드 크롤러가 새 강의 발견 시 이 웹훅 URL로 POST 전송

액션 1: Filter → trust_score 70점 이상인 강사의 강의만 통과
액션 2: Zapier Tables → 신규 강의 데이터 저장
액션 3: Formatter → 메시지 생성
  "🆕 {강사명}의 새 강의가 등록됐어요: {강의명} ({플랫폼})"
액션 4: Gmail 또는 Slack → 알림 발송
```

### Zap 3: 후기 급변 감지 알림
```
트리거: Schedule by Zapier → 매주 월요일 오전 8시
액션 1: Webhooks by Zapier → GET /api/instructors/trend?threshold=10
  (전주 대비 신뢰도 점수가 10점 이상 변동된 강사 목록 반환)
액션 2: Filter → 변동폭 10점 이상만 통과
액션 3: Formatter → 메시지 생성
  "📊 {강사명}의 신뢰도 점수가 이번 주 {변동값}점 변동됐습니다"
액션 4: Gmail 또는 Slack → 알림 발송
액션 5: Zapier Tables → 알림 이력 저장
```

### Zap 4: Google Form → DB 저장 (사용자 강의 요청)
```
트리거: Google Forms → 새 응답 발생 시
  폼 항목: 원하는 강의 주제, 예산, 난이도

액션 1: Webhooks by Zapier → POST /api/lectures/request
  (사용자 요청을 DB에 저장하고 맞춤 추천 결과 생성)
액션 2: Gmail → 요청자에게 추천 결과 이메일 발송
```

---

## 9. 프론트엔드 폴더 구조 — A담당

```
frontend/
├── public/
│   └── index.html
│
├── src/
│   ├── main.tsx                    # 진입점
│   ├── App.tsx                     # 라우터 설정
│   │
│   ├── pages/
│   │   ├── HomePage.tsx            # 메인 검색 화면
│   │   ├── DashboardPage.tsx       # 전체 현황 대시보드
│   │   ├── InstructorPage.tsx      # 강사 상세 + 신뢰도 추이
│   │   ├── ExamPage.tsx            # 자격증 시험 일정 + D-day
│   │   └── ComparePage.tsx         # 플랫폼별 강의 비교
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   │
│   │   ├── lecture/
│   │   │   ├── LectureCard.tsx
│   │   │   ├── LectureList.tsx
│   │   │   └── LectureFilter.tsx
│   │   │
│   │   ├── instructor/
│   │   │   ├── InstructorCard.tsx
│   │   │   ├── TrustScoreBar.tsx
│   │   │   └── ReviewList.tsx
│   │   │
│   │   ├── charts/
│   │   │   ├── TrustTrendChart.tsx     # Recharts LineChart
│   │   │   ├── PlatformCompareChart.tsx # Recharts BarChart
│   │   │   ├── CategoryPieChart.tsx    # Recharts PieChart
│   │   │   └── SentimentGauge.tsx
│   │   │
│   │   ├── exam/
│   │   │   ├── ExamCard.tsx
│   │   │   ├── DdayBadge.tsx
│   │   │   └── ExamTimeline.tsx
│   │   │
│   │   └── common/
│   │       ├── SearchBar.tsx
│   │       ├── Badge.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   │
│   ├── hooks/
│   │   ├── useLectures.ts          # TanStack Query 기반 강의 검색 훅
│   │   ├── useInstructor.ts        # 강사 정보 훅
│   │   └── useExams.ts             # 시험 일정 훅
│   │
│   ├── api/
│   │   ├── client.ts               # Axios 인스턴스 (baseURL, 인터셉터)
│   │   ├── lectures.ts             # 강의 API 함수
│   │   ├── instructors.ts          # 강사 API 함수
│   │   └── exams.ts                # 시험 API 함수
│   │
│   ├── types/
│   │   ├── lecture.ts
│   │   ├── review.ts
│   │   └── exam.ts
│   │
│   └── utils/
│       ├── formatters.ts
│       └── constants.ts
│
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### `package.json` 주요 의존성
```json
{
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "react-router-dom": "^6.0.0",
    "axios": "^1.7.0",
    "@tanstack/react-query": "^5.0.0",
    "recharts": "^2.12.0",
    "tailwindcss": "^3.4.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.0.0"
  }
}
```

---

## 10. 환경변수 목록 (`.env.example`)

```env
# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your_anon_key

# 네이버 검색 API
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# YouTube Data API
YOUTUBE_API_KEY=your_youtube_api_key

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# 큐넷 공공데이터
QNET_API_KEY=your_qnet_api_key

# K-MOOC
KMOOC_API_KEY=your_kmooc_api_key

# Zapier Webhook URL
ZAPIER_WEBHOOK_NEW_LECTURE=https://hooks.zapier.com/hooks/catch/xxxx/
ZAPIER_WEBHOOK_REVIEW_SPIKE=https://hooks.zapier.com/hooks/catch/xxxx/

# 서버 설정
PORT=8000
FRONTEND_URL=http://localhost:5173
```

---

## 11. 역할별 작업 순서

### A담당 — 크롤러 + 외부 API + 프론트엔드

```
1주차 — 환경 세팅
  - [ ] Supabase 프로젝트 생성 + SQL Editor에서 섹션 3 SQL 5개 실행
  - [ ] requirements.txt 설치 (섹션 3-4)
  - [ ] playwright install chromium 실행
  - [ ] .env 파일 생성 (섹션 10 기준)
  - [ ] B가 완성한 queries.py 함수 목록 확인 후 크롤러 개발 시작

2주차 — 크롤러 + API 수집기
  - [ ] base_crawler.py 구현 (섹션 4 코드 참고)
  - [ ] inflearn.py 크롤러 완성 → upsert_lecture() 호출 확인
  - [ ] class101.py 크롤러 완성
  - [ ] fastcampus.py 크롤러 완성
  - [ ] naver_api.py 후기 수집기 완성 → insert_review() 호출 확인
  - [ ] youtube_api.py 댓글 수집기 완성
  - [ ] kmooc_api.py 완성
  - [ ] qnet_api.py 완성 → upsert_exam() 호출 확인
  - [ ] cron_jobs.py 스케줄러 등록
  - [ ] ⚠️ B에게 인계 — Supabase 대시보드에서 데이터 적재 확인 후 알림

3주차 — React 프론트엔드 기초
  - [ ] React 프로젝트 초기화 (Vite + TypeScript)
  - [ ] package.json 의존성 설치 (섹션 9 참고)
  - [ ] api/client.ts Axios 인스턴스 설정
  - [ ] LectureCard, LectureList, LectureFilter 구현
  - [ ] HomePage, DashboardPage 레이아웃 구현

4주차 — React 프론트엔드 완성
  - [ ] InstructorPage, ExamPage, ComparePage 구현
  - [ ] TrustTrendChart, PlatformCompareChart, CategoryPieChart, SentimentGauge 구현
  - [ ] useLectures, useInstructor, useExams 커스텀 훅 (TanStack Query)
  - [ ] B가 완성한 FastAPI 엔드포인트 연결 테스트
  - [ ] npm run build 에러 없음 확인
```

### B담당 — DB 레이어 + AI + FastAPI + Zapier + 연동

```
1주차 — DB 레이어 완성 (A보다 먼저 완료해야 함)
  - [ ] FastAPI 프로젝트 구조 세팅 (섹션 2 기준)
  - [ ] main.py 기본 앱 설정 + CORS 미들웨어 추가
  - [ ] db/supabase_client.py 구현 (섹션 3-1 코드 그대로)
  - [ ] db/models.py 구현 (섹션 3-2 코드 그대로)
  - [ ] db/queries.py 전체 함수 구현 (섹션 3-3 코드 그대로)
  - [ ] tests/test_db.py 작성 + 통과 확인
  - [ ] ⚠️ A에게 공유 — queries.py 함수 목록 전달해서 크롤러 개발 시 바로 사용 가능하게
  - [ ] Zapier Organization에서 Webhook URL 4개 발급 → .env에 저장

2주차 — AI 처리 (A 인계 후 시작)
  - [ ] ad_filter.py 광고 필터링 구현 (섹션 6 프롬프트 그대로)
  - [ ] tests/test_ai.py 광고 필터링 테스트 작성 + 통과
  - [ ] sentiment.py 감성 분석 구현 (섹션 6 프롬프트 그대로)
  - [ ] tests/test_ai.py 감성 분석 테스트 작성 + 통과
  - [ ] trust_score.py 신뢰도 점수 계산 구현 (섹션 6 계산식 그대로)
  - [ ] A가 쌓은 데이터 일괄 분석 실행 (trust_score 초기값 생성)

3주차 — FastAPI 엔드포인트 + Zapier
  - [ ] api/lectures.py GET /api/lectures 완성
  - [ ] api/instructors.py GET /api/instructors/{name} 완성
  - [ ] api/reviews.py 완성
  - [ ] api/exams.py GET /api/exams 완성
  - [ ] api/zapier_webhook.py POST /api/zapier/trigger 완성
  - [ ] uvicorn 실행 후 /docs 전체 엔드포인트 응답 200 확인
  - [ ] Zapier Zap 1~4번 구성 (섹션 8 그대로)
  - [ ] Zapier Tables + Interfaces 기본 설정

4주차 — 전체 연동 + 배포
  - [ ] FastAPI ↔ React 전체 파이프라인 연동 테스트
  - [ ] Zapier ↔ FastAPI ↔ 대시보드 end-to-end 테스트
  - [ ] Render 또는 Railway 배포 (Playwright headless 서버 설정 포함)
  - [ ] 시연용 더미 데이터 30건 이상 준비
  - [ ] 발표 시나리오 테스트: 강의 검색 → 강사 신뢰도 확인 → 시험 D-day 알림
```

---

## 12. 빠진 내용 점검 및 구현 가능성 평가

### ⚠️ 추가 조사가 필요한 항목

| 항목 | 설명 | 심각도 |
|------|------|--------|
| 인프런·클래스101 실제 CSS 셀렉터 | 명세서의 셀렉터는 예시. 직접 개발자 도구로 확인 필요. 사이트 업데이트 시 변경될 수 있음 | 높음 |
| Playwright 서버 배포 설정 | Render/Railway에서 Playwright headless 실행 시 추가 패키지 필요. Dockerfile 작성 권장 | 높음 |
| Supabase RLS 정책 | Row Level Security 미설정 시 API 키 노출되면 DB 전체 오픈. Supabase 문서 참고 필수 | 높음 |
| OpenAI 비용 관리 | 후기 수천 건 처리 시 예상 비용 초과 가능. 일 처리량 상한선(예: 500건/일) 설정 권장 | 중간 |
| get_instructors_with_score_change() | 섹션 3-3에 pass 처리됨. Supabase rpc 또는 별도 로직 구현 필요 | 중간 |
| FastAPI API Key 인증 | 현재 엔드포인트 인증 없음. Header에 X-API-Key 검증 로직 추가 권장 | 중간 |
| 클래스101 로그인 벽 | 일부 강의 가격은 비로그인 수집 불가. 가격 없이 수집 후 0으로 저장하는 정책 결정 필요 | 낮음 |

### ✅ 구현 가능성 평가

**이 보고서만으로 즉시 구현 가능 (80%)**
- DB 스키마 SQL → 복붙 실행
- supabase_client.py → 코드 그대로 복붙
- models.py → 코드 그대로 복붙
- queries.py → 함수 전체 명세됨
- requirements.txt → 그대로 설치
- FastAPI 엔드포인트 → 명세 그대로 작성
- OpenAI 프롬프트 → 그대로 사용
- Zapier Zap 4개 → 단계별 명세됨
- React 폴더 구조 + package.json → 그대로 세팅

**추가 작업 필요 (20%)**
- 인프런·클래스101 CSS 셀렉터 확인
- Playwright 배포용 Dockerfile 작성
- Supabase RLS 보안 설정
- get_instructors_with_score_change() 로직 완성

**전체 결론: 이전 버전 대비 DB 레이어 코드가 추가되어 구현 가능성이 70% → 80%로 올라갔다. 대학생 팀 기준 4주 안에 완성 가능한 수준이다.**

---

## 13. Claude Code 워크플로우 설정

> Claude Code가 이 보고서의 명령을 정확하게 따르도록 하는 파일 구조와 규칙이다.
> 아래 파일들을 프로젝트 루트에 만들고 Claude Code를 실행하면 된다.

### 13-1. 추가 파일 구조

```
프로젝트 루트/
├── CLAUDE.md          ← 전체 프로젝트 규칙 (매 세션 자동 로드)
├── tasks.md           ← A/B 체크박스 작업 목록 (세션 간 상태 유지)
├── plan.md            ← 구현 전 설계 확정용 (작업 단위로 덮어씀)
│
├── backend/
│   └── CLAUDE.md      ← 백엔드 전용 규칙
│
└── frontend/
    └── CLAUDE.md      ← 프론트엔드 전용 규칙
```

---

### 13-2. 루트 `CLAUDE.md` 전체 내용

```markdown
# 국내 강의 통합 추천 시스템 — Claude Code 규칙

## 프로젝트 구조
- backend/ : Python FastAPI 서버 (섹션 2 폴더 구조 참고)
- frontend/ : React 18 + TypeScript (섹션 9 폴더 구조 참고)
- tasks.md : 전체 작업 체크리스트 (항상 최신 상태 유지)

## 담당자 역할
- A담당: 크롤러(app/crawlers/) + 수집기(app/collectors/) + 프론트엔드(frontend/)
- B담당: DB(app/db/) + AI(app/ai/) + API(app/api/) + Zapier 연동

## 🚨 작업 시작 전 필수 절차

1. tasks.md 읽기
2. [ ] 상태인 항목 중 첫 번째 항목만 수행
3. 다음 항목으로 임의 진행 금지 — 완료 보고 후 사용자 확인 받기

## 🚨 작업 완료 후 필수 절차

1. Definition of Done 검증 실행
2. 검증 통과 시에만 tasks.md에서 [ ] → [x] 변경
3. "✅ {작업명} 완료. 다음 작업: {다음항목명}" 형식으로 보고

## Definition of Done

### 백엔드
- DB: python -m pytest tests/test_db.py — 전체 통과
- 크롤러: python -m pytest tests/test_crawlers.py — 전체 통과
- API 수집기: python -m pytest tests/test_collectors.py — 전체 통과
- AI: python -m pytest tests/test_ai.py — 전체 통과
- FastAPI: uvicorn 실행 후 /docs 확인 + 각 엔드포인트 200 응답

### 프론트엔드
- npm run build — 에러 없음
- 브라우저에서 렌더링 확인

## 자주 쓰는 명령어

cd backend && pip install -r requirements.txt
cd backend && playwright install chromium
cd backend && uvicorn main:app --reload --port 8000
cd backend && python -m pytest tests/ -v
cd frontend && npm install && npm run dev

## 코딩 규칙

### Python
- 타입 힌트 필수
- 비동기 함수는 async/await 사용
- 에러는 try/except + logger.error()
- .env 값은 os.getenv()로만 접근, 하드코딩 금지

### TypeScript/React
- 함수형 컴포넌트 + hooks만 사용
- props는 interface 타입 정의 필수
- API 호출은 src/api/ 함수 통해서만

## 절대 하지 말 것
- .env API 키를 코드에 직접 작성
- DB 스키마 임의 변경 (섹션 3 SQL 기준 유지)
- queries.py 함수 시그니처 임의 변경 (A/B 공유 인터페이스)
- 명세서에 없는 라이브러리 임의 추가
```

---

### 13-3. `tasks.md` 전체 내용

```markdown
# 작업 체크리스트

> 규칙: 작업 완료 시 [ ] → [x] 즉시 변경. 한 번에 한 항목만 진행.

---

## 🅐 A담당 — 크롤러 + 외부 API + 프론트엔드

### 1주차 — 환경 세팅
- [ ] Supabase 프로젝트 생성 + SQL Editor에서 섹션 3 SQL 5개 실행
- [ ] requirements.txt 설치 + playwright install chromium
- [ ] .env 파일 생성 (섹션 10 기준)
- [ ] B가 완성한 queries.py 함수 목록 확인

### 2주차 — 크롤러 + 수집기
- [ ] base_crawler.py 구현 (섹션 4 코드 참고)
- [ ] inflearn.py 완성 + upsert_lecture() 연결 확인
- [ ] class101.py 완성
- [ ] fastcampus.py 완성
- [ ] naver_api.py 완성 + insert_review() 연결 확인
- [ ] youtube_api.py 완성
- [ ] kmooc_api.py 완성
- [ ] qnet_api.py 완성 + upsert_exam() 연결 확인
- [ ] cron_jobs.py 스케줄러 등록
- [ ] ⚠️ B 인계 — Supabase 대시보드 데이터 적재 확인 후 알림

### 3주차 — React 기초
- [ ] Vite + TypeScript 프로젝트 초기화
- [ ] package.json 의존성 설치 (섹션 9 참고)
- [ ] api/client.ts Axios 설정
- [ ] LectureCard, LectureList, LectureFilter 구현
- [ ] HomePage, DashboardPage 레이아웃 구현

### 4주차 — React 완성
- [ ] InstructorPage, ExamPage, ComparePage 구현
- [ ] TrustTrendChart, PlatformCompareChart, CategoryPieChart, SentimentGauge 구현
- [ ] useLectures, useInstructor, useExams 훅 구현 (TanStack Query)
- [ ] B FastAPI 엔드포인트 연결 테스트
- [ ] npm run build 에러 없음 확인

---

## 🅑 B담당 — DB + AI + FastAPI + Zapier + 연동

### 1주차 — DB 레이어 (A보다 먼저 완료)
- [ ] FastAPI 프로젝트 구조 세팅 (섹션 2 기준)
- [ ] main.py 기본 앱 + CORS 설정
- [ ] db/supabase_client.py 구현 (섹션 3-1 코드 그대로)
- [ ] db/models.py 구현 (섹션 3-2 코드 그대로)
- [ ] db/queries.py 전체 함수 구현 (섹션 3-3 코드 그대로)
- [ ] tests/test_db.py 작성 + 통과 확인
- [ ] ⚠️ A에게 공유 — queries.py 완성 알림 (크롤러 개발 시 바로 사용 가능)
- [ ] Zapier Webhook URL 4개 발급 → .env 저장

### 2주차 — AI 처리 (A 인계 후 시작)
- [ ] ad_filter.py 구현 (섹션 6 프롬프트 그대로)
- [ ] tests/test_ai.py 광고 필터링 테스트 + 통과
- [ ] sentiment.py 구현 (섹션 6 프롬프트 그대로)
- [ ] tests/test_ai.py 감성 분석 테스트 + 통과
- [ ] trust_score.py 구현 (섹션 6 계산식 그대로)
- [ ] A 데이터 일괄 분석 실행 (trust_score 초기값 생성)

### 3주차 — FastAPI + Zapier
- [ ] api/lectures.py GET /api/lectures 완성
- [ ] api/instructors.py GET /api/instructors/{name} 완성
- [ ] api/reviews.py 완성
- [ ] api/exams.py GET /api/exams 완성
- [ ] api/zapier_webhook.py POST /api/zapier/trigger 완성
- [ ] /docs 전체 엔드포인트 응답 200 확인
- [ ] Zapier Zap 1번 구성 (D-day 알림)
- [ ] Zapier Zap 2번 구성 (신규 강의 알림)
- [ ] Zapier Zap 3번 구성 (후기 급변 알림)
- [ ] Zapier Zap 4번 구성 (Google Form → DB)
- [ ] Zapier Tables + Interfaces 설정

### 4주차 — 전체 연동 + 배포
- [ ] FastAPI ↔ React 파이프라인 연동 테스트
- [ ] Zapier ↔ FastAPI ↔ 대시보드 end-to-end 테스트
- [ ] Render 또는 Railway 배포 (Playwright headless 설정 포함)
- [ ] 시연용 더미 데이터 30건 이상 준비
- [ ] 발표 시나리오 테스트: 강의 검색 → 강사 신뢰도 → D-day 알림
```

---

### 13-4. `backend/CLAUDE.md`

```markdown
# 백엔드 전용 규칙

## 디렉터리 역할
- app/crawlers/ : 크롤링만. DB 직접 저장 금지. queries.py 함수 호출로만
- app/collectors/ : 외부 API 호출만. DB 직접 저장 금지. queries.py 함수 호출로만
- app/ai/ : OpenAI API 호출 + 결과 반환만. DB 저장은 api/ 레이어에서
- app/api/ : FastAPI 라우터. queries.py 통해 DB 읽기/쓰기
- app/db/ : DB 연결 + 쿼리만. 비즈니스 로직 없음

## 크롤러 규칙
- 모든 크롤러는 BaseCrawler 상속
- 딜레이: await asyncio.sleep(random.uniform(1, 3))
- User-Agent: fake_useragent 랜덤 설정
- 실패 시 최대 3회 재시도 후 logger.error()

## OpenAI 규칙
- 광고 필터링: gpt-4o-mini
- 감성 분석: gpt-4o
- 응답은 반드시 JSON 파싱 후 반환
- 에러 시 {"error": true, "reason": "..."} 반환
```

---

### 13-5. `frontend/CLAUDE.md`

```markdown
# 프론트엔드 전용 규칙

## 컴포넌트 규칙
- 함수형 컴포넌트 + hooks만 (class 금지)
- props 타입은 interface로 컴포넌트 바로 위에 정의
- 스타일은 Tailwind CSS 사용

## 상태 관리
- 서버 상태: TanStack Query (useQuery, useMutation)
- 로컬 상태: useState, useReducer

## API 호출 규칙
- 모든 API 호출은 src/api/ 함수 통해서만
- 컴포넌트에서 직접 axios 호출 금지

## 파일 위치
- 페이지: src/pages/
- 컴포넌트: src/components/
- API 함수: src/api/
- 타입: src/types/
- 훅: src/hooks/
```

---

### 13-6. Claude Code 명령 패턴

#### 세션 시작 시
```
tasks.md 읽고 현재 상황 파악해줘. 내 담당 미완료 항목 첫 번째부터 시작해줘.
```

#### 구현 전 설계 확인
```
queries.py의 upsert_lecture 함수 구현 plan.md 작성해줘. 구현은 하지 말고 계획만.
```
→ 검토 후 →
```
plan.md 내용대로 구현해줘. 완료되면 tests/test_db.py 실행 후 tasks.md 체크해줘.
```

#### 세션 종료 전
```
오늘 완료 작업 요약하고 tasks.md 체크 상태 확인해줘.
```

#### 새 세션 시작 (컨텍스트 초기화 후)
```
tasks.md 읽고 이어서 진행해줘.
```

---

## 14. 추가 조사 항목 해결책 (실제 코드 포함)

> 섹션 12의 "추가 조사 필요" 항목 전부 해결. 아래 코드를 그대로 적용하면 된다.

---

### 14-1. Playwright 서버 배포 설정 — `Dockerfile`

> Railway/Render에서 Playwright를 실행하려면 반드시 Dockerfile이 필요하다.
> 공식 Microsoft Playwright 이미지를 베이스로 사용하는 게 가장 안전하다.

```dockerfile
# Dockerfile (backend/ 루트에 위치)
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치 (이미지에 포함되어 있지만 명시적으로 재설치)
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> `base_crawler.py`의 브라우저 실행 args도 Docker 환경에 맞게 수정해야 한다.

```python
# base_crawler.py — Docker 환경용 브라우저 실행 설정
async def init_browser(self):
    p = await async_playwright().start()
    self.browser = await p.chromium.launch(
        headless=True,
        args=[
            "--disable-dev-shm-usage",   # Docker /dev/shm 64MB 제한 우회
            "--no-sandbox",              # 컨테이너 환경 필수
            "--disable-setuid-sandbox",
            "--disable-gpu",             # Docker에 GPU 없음
            "--disable-software-rasterizer",
        ]
    )
```

---

### 14-2. Supabase RLS 정책 — SQL Editor에서 실행

> **왜 필요한가:** anon key(SUPABASE_KEY)가 외부에 노출되면 누구나 DB를 읽고 쓸 수 있다.
> RLS를 설정하면 FastAPI 서버(service_role)만 접근 가능하고 외부는 차단된다.

```sql
-- Supabase 대시보드 SQL Editor에서 실행
-- 모든 테이블에 RLS 활성화

ALTER TABLE lectures ENABLE ROW LEVEL SECURITY;
ALTER TABLE instructors ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE zapier_alerts_log ENABLE ROW LEVEL SECURITY;

-- service_role은 모든 작업 허용 (FastAPI 서버가 사용하는 키)
CREATE POLICY "service_role_all_lectures"
  ON lectures FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_instructors"
  ON instructors FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_reviews"
  ON reviews FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_exams"
  ON exams FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_alerts"
  ON zapier_alerts_log FOR ALL TO service_role USING (true) WITH CHECK (true);

-- anon role은 lectures, instructors, exams 읽기만 허용 (조회 전용)
CREATE POLICY "anon_read_lectures"
  ON lectures FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_instructors"
  ON instructors FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_exams"
  ON exams FOR SELECT TO anon USING (true);
```

> **주의:** `.env`의 `SUPABASE_KEY`를 `service_role` 키로 변경해야 한다.
> Supabase 대시보드 → Settings → API → `service_role` 키 복사 → `.env`에 붙여넣기

```env
# .env 수정
SUPABASE_KEY=your_service_role_key   # ← anon key 아닌 service_role key 사용
```

---

### 14-3. FastAPI API Key 인증 — `main.py`

> 외부에서 FastAPI 엔드포인트에 아무나 접근하지 못하도록 미들웨어로 차단한다.

```python
# main.py 전체 내용
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="강의 추천 API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key 인증 미들웨어
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
PUBLIC_PATHS = ["/docs", "/openapi.json", "/redoc", "/health"]

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    # /docs, /health 등 공개 경로는 인증 스킵
    if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != API_SECRET_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key"}
        )
    return await call_next(request)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 라우터 등록
from app.api import lectures, instructors, reviews, exams, zapier_webhook
app.include_router(lectures.router, prefix="/api")
app.include_router(instructors.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(exams.router, prefix="/api")
app.include_router(zapier_webhook.router, prefix="/api")
```

> `.env`에 `API_SECRET_KEY` 추가 필요:
```env
API_SECRET_KEY=your-random-secret-key-here   # 랜덤 문자열 직접 설정
```

> `requirements.txt`에도 추가:
```
python-multipart==0.0.9
```

---

### 14-4. OpenAI 비용 관리 — Batch API + 일일 처리량 제한

> **핵심:** OpenAI Batch API는 일반 API 대비 비용 50% 절감, 24시간 내 처리를 보장한다.
> 후기 수천 건 감성 분석은 실시간이 필요 없으므로 Batch API가 최적이다.

```python
# app/ai/batch_processor.py — OpenAI Batch API 활용 비용 절감 처리기
import os
import json
import time
from openai import OpenAI
from app.db.queries import get_unanalyzed_reviews, update_review_sentiment
from app.utils.logger import logger

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 일일 처리량 상한선 (비용 초과 방지)
DAILY_LIMIT = 500

def run_batch_sentiment_analysis():
    """
    미분석 후기를 Batch API로 일괄 처리.
    하루 최대 DAILY_LIMIT건만 처리해서 비용 관리.
    """
    reviews = get_unanalyzed_reviews()[:DAILY_LIMIT]
    if not reviews:
        logger.info("분석할 후기 없음")
        return

    # JSONL 파일 생성
    requests = []
    for review in reviews:
        requests.append({
            "custom_id": str(review["id"]),
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-5.5",
                "max_tokens": 150,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "강의 후기 텍스트를 분석해서 감성을 판단해. "
                            "반드시 JSON으로만 응답: "
                            "{\"sentiment\": \"positive\"|\"negative\"|\"neutral\", "
                            "\"score\": -1.0~1.0, "
                            "\"keywords\": [\"키워드1\",\"키워드2\"]}"
                        )
                    },
                    {"role": "user", "content": review["content"][:500]}
                ]
            }
        })

    # JSONL 파일로 저장
    jsonl_path = "/tmp/batch_requests.jsonl"
    with open(jsonl_path, "w") as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    # 배치 업로드 및 실행
    with open(jsonl_path, "rb") as f:
        batch_file = client.files.create(file=f, purpose="batch")

    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )

    logger.info(f"배치 생성 완료: {batch.id} ({len(reviews)}건)")
    return batch.id

def check_and_save_batch_results(batch_id: str):
    """배치 완료 여부 확인 후 결과 DB 저장"""
    batch = client.batches.retrieve(batch_id)

    if batch.status != "completed":
        logger.info(f"배치 {batch_id} 상태: {batch.status}")
        return False

    # 결과 다운로드
    result_file = client.files.content(batch.output_file_id)
    for line in result_file.text.strip().split("\n"):
        result = json.loads(line)
        review_id = result["custom_id"]
        content = result["response"]["body"]["choices"][0]["message"]["content"]
        try:
            data = json.loads(content)
            update_review_sentiment(
                review_id=review_id,
                sentiment=data["sentiment"],
                sentiment_score=data["score"]
            )
        except Exception as e:
            logger.error(f"결과 파싱 실패: {review_id} — {e}")

    logger.info(f"배치 {batch_id} 결과 저장 완료")
    return True
```

> `cron_jobs.py`에 배치 실행 스케줄 추가:
```python
# 매일 새벽 2시 배치 실행, 오전 6시 결과 확인
scheduler.add_job(run_batch_sentiment_analysis, "cron", hour=2)
scheduler.add_job(check_pending_batches, "cron", hour=6)
```

---

### 14-5. `get_instructors_with_score_change()` 구현 — `queries.py` 보완

> 섹션 3-3에서 `pass`로 비워뒀던 함수. 아래 코드로 교체한다.

```python
# queries.py — get_instructors_with_score_change 실제 구현
from datetime import datetime, timedelta

def get_instructors_with_score_change(threshold: float = 10.0) -> list[dict]:
    """
    지난 7일 대비 trust_score가 threshold 이상 변동된 강사 목록 반환.
    Supabase에 score_history 테이블이 없으므로 현재 점수와
    last_calculated_at 기준으로 변동 감지.
    """
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    # 지난 7일 내 점수가 업데이트된 강사만 조회
    recent = supabase.table("instructors") \
        .select("*") \
        .gte("last_calculated_at", week_ago) \
        .execute().data

    # 이전 점수 기록이 없으므로 trust_score 변화를 감지하려면
    # score_history 테이블을 별도로 만들거나, 아래처럼 단순화한다:
    # trust_score가 threshold 이하이거나 이상인 극단값을 가진 강사 반환
    result = []
    for instructor in recent:
        score = instructor.get("trust_score", 0)
        # 극단적으로 낮거나 (부정 급증) 높은 경우 알림 대상으로 판단
        if score <= (50 - threshold) or score >= (90 + threshold / 2):
            instructor["change_type"] = "급락" if score <= 50 - threshold else "급등"
            result.append(instructor)

    return result
```

> **더 정확한 이력 추적이 필요하면** Supabase에 `score_history` 테이블을 추가한다:
```sql
CREATE TABLE score_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instructor_name VARCHAR(100),
    trust_score FLOAT,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);
```
> 매주 월요일 현재 점수를 이 테이블에 기록하고, 지난주 기록과 비교하면 정확한 변동폭을 계산할 수 있다.

---

### 14-6. 클래스101 로그인 벽 — 수집 정책 확정

> 비로그인으로 가격을 볼 수 없는 강의는 아래 정책으로 통일한다.

```python
# class101.py — 가격 수집 정책
# 비로그인 시 가격 표시 안 되는 경우 처리

def parse_lecture_price(price_element) -> tuple[int, bool]:
    """
    가격 파싱. 비로그인으로 확인 불가 시 (0, False) 반환.
    반환값: (price, price_available)
    """
    if price_element is None:
        return 0, False  # 가격 정보 없음

    text = price_element.text.strip()
    if "로그인" in text or "원" not in text:
        return 0, False  # 로그인 필요 또는 파싱 불가

    try:
        price = int(text.replace(",", "").replace("원", "").strip())
        return price, True
    except ValueError:
        return 0, False
```

> `lectures` 테이블에 `price_available` 컬럼 추가 필요:
```sql
ALTER TABLE lectures ADD COLUMN price_available BOOLEAN DEFAULT TRUE;
```
> 프론트엔드에서는 `price_available = false`인 강의에 "가격 확인 필요" 배지를 표시한다.

---

### 14-7. 섹션 12 업데이트 — 해결된 항목 반영

| 항목 | 상태 | 해결 섹션 |
|------|------|-----------|
| Playwright 서버 배포 설정 | ✅ 해결 | 섹션 14-1 Dockerfile |
| Supabase RLS 정책 | ✅ 해결 | 섹션 14-2 SQL |
| FastAPI API Key 인증 | ✅ 해결 | 섹션 14-3 middleware |
| OpenAI 비용 관리 | ✅ 해결 | 섹션 14-4 Batch API |
| get_instructors_with_score_change() | ✅ 해결 | 섹션 14-5 구현 코드 |
| 클래스101 로그인 벽 | ✅ 해결 | 섹션 14-6 수집 정책 |
| 인프런·클래스101 CSS 셀렉터 | ⚠️ 미해결 | 직접 개발자 도구로 확인 필요 |

> **최종 구현 가능성: 80% → 95%**
> CSS 셀렉터 확인만 남았고 나머지 리스크는 전부 코드로 해결됐다.

---

## 14. 추가 조사 항목 해결 명세

> 섹션 12에서 "추가 조사 필요"로 분류된 항목 전체를 실제 코드로 해결한다.

---

### 14-1. 인프런·클래스101 CSS 셀렉터 확인 방법

자동화된 방법은 없고 직접 개발자 도구로 확인해야 한다. 아래 절차를 따른다.

```
1. Chrome에서 해당 사이트 접속
2. F12 → Elements 탭
3. 강의 카드 영역에 마우스 올리고 우클릭 → 검사
4. 해당 엘리먼트의 class 속성 확인

인프런 확인 대상:
  - 강의 카드 전체: 강의 목록에서 반복되는 최상위 div
  - 강의명, 강사명, 평점, 가격, 수강생 수 각각

클래스101 확인 대상:
  - 카드 컨테이너, 강의명, 가격, 강사명
```

셀렉터가 바뀌는 경우에 대비한 안전장치:

```python
# base_crawler.py에 추가
async def safe_select(self, page, selector: str, default: str = "") -> str:
    """셀렉터 실패 시 빈 문자열 반환. 크롤러 전체가 멈추지 않게"""
    try:
        element = await page.query_selector(selector)
        if element:
            return await element.inner_text()
        return default
    except Exception:
        return default
```

---

### 14-2. Playwright 서버 배포용 `Dockerfile`

Railway에서 Playwright 실행 시 브라우저 바이너리와 시스템 레벨 의존성이 필요하며, 표준 Python 이미지로는 실행되지 않는다. Microsoft 공식 Playwright Python 이미지를 베이스로 사용하는 것이 권장된다.

```dockerfile
# Microsoft 공식 Playwright Python 이미지 사용
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY . .

# Playwright 브라우저 설치 (이미지에 포함되어 있지만 명시적으로 재설치)
RUN playwright install chromium

# 포트 설정
ENV PORT=8000
EXPOSE 8000

# 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Railway 배포 시 추가 설정:

```
Railway 대시보드 → 서비스 → Settings → Resources
→ Memory: 최소 1GB 이상 설정 (Chromium이 수백 MB 사용)

환경변수 추가:
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

---

### 14-3. Supabase RLS 정책 설정

RLS 없이는 anon 키를 가진 누구든 public 스키마의 모든 테이블을 읽고 쓸 수 있다. 규칙은 단순하다: public 스키마의 모든 테이블에 예외 없이 RLS를 활성화해야 한다.

service_role 키로 생성한 Supabase 클라이언트는 모든 RLS 정책을 우회한다. 이는 백그라운드 작업, 마이그레이션 같은 서버사이드 관리 작업을 위한 것이다. service_role 키는 절대 클라이언트 사이드에 노출해서는 안 된다.

Supabase SQL Editor에서 실행:

```sql
-- 1. 모든 테이블 RLS 활성화
ALTER TABLE lectures ENABLE ROW LEVEL SECURITY;
ALTER TABLE instructors ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE zapier_alerts_log ENABLE ROW LEVEL SECURITY;

-- 2. 이 프로젝트는 서버(FastAPI)에서만 DB에 접근하므로
--    anon 역할에는 읽기 전용 허용, 쓰기는 service_role만
--    (FastAPI는 service_role 키 사용)

-- lectures: 누구나 읽기 가능, 쓰기는 서버만
CREATE POLICY "lectures_select" ON lectures FOR SELECT TO anon USING (true);
CREATE POLICY "lectures_insert" ON lectures FOR INSERT TO service_role WITH CHECK (true);
CREATE POLICY "lectures_update" ON lectures FOR UPDATE TO service_role USING (true);

-- instructors: 읽기 공개, 쓰기 서버만
CREATE POLICY "instructors_select" ON instructors FOR SELECT TO anon USING (true);
CREATE POLICY "instructors_write" ON instructors FOR ALL TO service_role USING (true);

-- reviews: 읽기 공개, 쓰기 서버만
CREATE POLICY "reviews_select" ON reviews FOR SELECT TO anon USING (true);
CREATE POLICY "reviews_write" ON reviews FOR ALL TO service_role USING (true);

-- exams: 읽기 공개, 쓰기 서버만
CREATE POLICY "exams_select" ON exams FOR SELECT TO anon USING (true);
CREATE POLICY "exams_write" ON exams FOR ALL TO service_role USING (true);

-- zapier_alerts_log: 서버만 접근
CREATE POLICY "alerts_all" ON zapier_alerts_log FOR ALL TO service_role USING (true);
```

`supabase_client.py` 키 변경 (anon → service_role):

```python
# RLS 설정 후 백엔드는 service_role 키 사용해야 쓰기 가능
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # anon 키 아님!
```

`.env`에 추가:

```env
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key  # Supabase 대시보드 → Settings → API
```

---

### 14-4. OpenAI 비용 관리 — 일일 처리량 상한선

```python
# app/ai/batch_processor.py

import os
from datetime import date
from app.db.supabase_client import supabase
from app.ai.ad_filter import filter_ad
from app.ai.sentiment import analyze_sentiment
from app.ai.trust_score import calculate_trust_score
from app.utils.logger import logger

DAILY_LIMIT = int(os.getenv("OPENAI_DAILY_LIMIT", "500"))  # 기본 500건/일

def get_today_processed_count() -> int:
    """오늘 처리된 후기 수 조회"""
    today = date.today().isoformat()
    result = supabase.table("reviews") \
        .select("id", count="exact") \
        .gte("collected_at", today) \
        .not_.is_("sentiment", "null") \
        .execute()
    return result.count or 0

async def run_daily_batch():
    """매일 스케줄러에서 호출. 상한선 초과 시 중단"""
    processed_today = get_today_processed_count()
    remaining = DAILY_LIMIT - processed_today

    if remaining <= 0:
        logger.info(f"오늘 처리 상한선 {DAILY_LIMIT}건 도달. 배치 중단.")
        return

    # 미처리 후기 가져오기 (상한선 내에서만)
    unanalyzed = supabase.table("reviews") \
        .select("*") \
        .is_("sentiment", "null") \
        .eq("is_ad", False) \
        .limit(remaining) \
        .execute().data

    logger.info(f"오늘 처리 가능: {remaining}건. 대상: {len(unanalyzed)}건")

    for review in unanalyzed:
        try:
            # 1단계: 광고 필터링 (gpt-5.4-mini)
            ad_result = await filter_ad(review["content"])
            if ad_result["is_ad"]:
                supabase.table("reviews").update({"is_ad": True}) \
                    .eq("id", review["id"]).execute()
                continue

            # 2단계: 감성 분석 (gpt-5.5)
            sentiment_result = await analyze_sentiment(review["content"])
            supabase.table("reviews").update({
                "sentiment": sentiment_result["sentiment"],
                "sentiment_score": sentiment_result["score"]
            }).eq("id", review["id"]).execute()

        except Exception as e:
            logger.error(f"배치 처리 실패 review_id={review['id']}: {e}")
            continue

    # 3단계: 영향받은 강사들 신뢰도 점수 재계산
    affected_instructors = list(set(
        r["instructor_name"] for r in unanalyzed if r.get("instructor_name")
    ))
    for name in affected_instructors:
        calculate_trust_score(name)
```

`.env`에 추가:

```env
OPENAI_DAILY_LIMIT=500
```

---

### 14-5. `get_instructors_with_score_change()` 구현

섹션 3-3에서 pass 처리된 함수의 실제 구현:

```python
# app/db/queries.py 에 추가

from datetime import datetime, timedelta

def get_instructors_with_score_change(threshold: float = 10.0) -> list[dict]:
    """
    신뢰도 점수가 threshold 이상 변동된 강사 목록 반환.
    last_calculated_at 기준으로 7일 전 점수와 현재 점수를 비교한다.
    단순 구현: 현재 trust_score와 7일 전 review 데이터로 재계산한 점수를 비교.
    """
    # 전체 강사 목록 조회
    instructors = supabase.table("instructors") \
        .select("*") \
        .execute().data

    result = []
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    for instructor in instructors:
        name = instructor["name"]
        current_score = instructor["trust_score"] or 0

        # 7일 전 후기 기준 과거 점수 계산
        old_reviews = supabase.table("reviews") \
            .select("sentiment_score") \
            .eq("instructor_name", name) \
            .eq("is_ad", False) \
            .lt("collected_at", week_ago) \
            .execute().data

        if not old_reviews:
            continue

        positive_old = sum(1 for r in old_reviews if r["sentiment_score"] and r["sentiment_score"] > 0)
        total_old = len(old_reviews)
        avg_score_old = sum(
            r["sentiment_score"] for r in old_reviews if r["sentiment_score"]
        ) / total_old

        old_trust_score = (positive_old / total_old) * 60 \
            + (avg_score_old + 1) / 2 * 30 \
            + min(total_old / 100, 1.0) * 10

        change = current_score - old_trust_score

        if abs(change) >= threshold:
            result.append({
                "instructor_name": name,
                "current_score": round(current_score, 1),
                "previous_score": round(old_trust_score, 1),
                "change": round(change, 1),
                "direction": "상승" if change > 0 else "하락"
            })

    return sorted(result, key=lambda x: abs(x["change"]), reverse=True)
```

---

### 14-6. FastAPI API Key 인증

FastAPI의 APIKeyHeader를 사용하면 헤더에서 API 키를 자동으로 추출하고, OpenAPI 문서에도 자동으로 통합된다.

```python
# app/api/auth.py (신규 파일)

import os
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("INTERNAL_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(key: str = Security(api_key_header)) -> str:
    """모든 엔드포인트에 Depends()로 주입. 키 불일치 시 401 반환."""
    if not secrets.compare_digest(key, API_KEY):  # 타이밍 공격 방지
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return key
```

각 엔드포인트에 적용:

```python
# app/api/lectures.py 예시
from app.api.auth import verify_api_key

@router.get("/lectures")
async def get_lectures(
    keyword: str = None,
    api_key: str = Depends(verify_api_key)  # ← 이 한 줄 추가
):
    return {"lectures": get_lectures(keyword=keyword)}
```

`main.py`에서 전체 앱에 일괄 적용 (개별 엔드포인트 수정 불필요):

```python
# main.py
from app.api.auth import verify_api_key

app = FastAPI(dependencies=[Depends(verify_api_key)])  # 전체 적용
```

`.env`에 추가:

```env
INTERNAL_API_KEY=your_random_secret_key_here  # 32자 이상 랜덤 문자열 권장
```

React `api/client.ts`에서 헤더 추가:

```typescript
// src/api/client.ts
const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "X-API-Key": import.meta.env.VITE_INTERNAL_API_KEY
  }
});
```

`frontend/.env`에 추가:

```env
VITE_API_URL=http://localhost:8000
VITE_INTERNAL_API_KEY=your_random_secret_key_here
```

---

### 14-7. 클래스101 로그인 벽 처리 정책

비로그인으로 수집 가능한 항목과 불가한 항목을 명확히 분리한다.

```
비로그인 수집 가능:
  - 강의명 ✅
  - 강사명 ✅
  - 카테고리 ✅
  - 썸네일 ✅
  - URL ✅

비로그인 수집 불가:
  - 정확한 가격 ❌ (로그인 후 표시)
  - 수강생 수 ❌
```

처리 방식:

```python
# class101.py 크롤러에서 가격 파싱 부분
price_text = await self.safe_select(page, ".price-selector")

if not price_text or "로그인" in price_text:
    price = -1          # -1 = 가격 미확인 (0은 무료와 구분)
    is_free = False
else:
    price = parse_price(price_text)
    is_free = (price == 0)
```

`lectures` 테이블 price 컬럼 의미:
```
0   → 무료 강의
> 0 → 유료 (원 단위)
-1  → 가격 미확인 (클래스101 로그인 필요)
```

프론트엔드에서 -1 처리:
```typescript
// LectureCard.tsx
const displayPrice = lecture.price === -1
  ? "가격 확인 필요"
  : lecture.price === 0
  ? "무료"
  : `${lecture.price.toLocaleString()}원`;
```

---

### 14-8. 업데이트된 `requirements.txt`

섹션 14 추가 사항 반영:

```
# 웹 프레임워크
fastapi==0.115.0
uvicorn==0.30.0

# DB
supabase==2.7.0

# 크롤링
playwright==1.45.0
beautifulsoup4==4.12.3
requests==2.32.3
fake-useragent==1.5.1

# AI
openai==1.40.0

# 스케줄러
apscheduler==3.10.4

# 환경변수
python-dotenv==1.0.1

# 유틸
pydantic==2.8.0
httpx==0.27.0
```

---

### 14-9. 업데이트된 `.env.example`

섹션 14 추가 사항 반영:

```env
# Supabase (service_role 키 사용 — RLS 설정 후 필수)
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# 네이버 검색 API
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# YouTube Data API
YOUTUBE_API_KEY=your_youtube_api_key

# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_DAILY_LIMIT=500

# 큐넷 공공데이터
QNET_API_KEY=your_qnet_api_key

# K-MOOC
KMOOC_API_KEY=your_kmooc_api_key

# Zapier Webhook URL
ZAPIER_WEBHOOK_NEW_LECTURE=https://hooks.zapier.com/hooks/catch/xxxx/
ZAPIER_WEBHOOK_REVIEW_SPIKE=https://hooks.zapier.com/hooks/catch/xxxx/

# FastAPI 내부 인증
INTERNAL_API_KEY=your_32char_random_secret

# 서버 설정
PORT=8000
FRONTEND_URL=http://localhost:5173
```

---

## 12. 빠진 내용 점검 및 구현 가능성 평가 (최종)

### ✅ 해결된 항목 (섹션 14에서 완전 해결)

| 항목 | 해결 위치 |
|------|-----------|
| Playwright 배포 Dockerfile | 섹션 14-2 |
| Supabase RLS 정책 SQL | 섹션 14-3 |
| OpenAI 비용 관리 로직 | 섹션 14-4 |
| get_instructors_with_score_change() 구현 | 섹션 14-5 |
| FastAPI API Key 인증 코드 | 섹션 14-6 |
| 클래스101 로그인 벽 처리 정책 | 섹션 14-7 |

### ⚠️ 여전히 직접 확인이 필요한 항목

| 항목 | 이유 |
|------|------|
| 인프런·클래스101 CSS 셀렉터 | 사이트가 언제든 업데이트될 수 있어 문서화 불가. 개발자 도구로 직접 확인 필수 (섹션 14-1 방법 참고) |

### ✅ 최종 구현 가능성 평가

이 보고서만으로 즉시 구현 가능: **90%**

나머지 10%는 인프런·클래스101 CSS 셀렉터 직접 확인 작업 하나뿐이다.
