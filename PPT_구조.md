# PPT 구성안 — 국내 강의 통합 추천 시스템

---

## 슬라이드 1 — 서비스 개요

**제목**: 국내 강의 통합 추천 시스템

- 자연어 질문 → AI 학습 로드맵 생성 → 강의 추천
- 17개 플랫폼 강의 통합 검색
- 추천 결과 이메일 발송

**접속 주소**: https://2026-ai-service-project.vercel.app

---

## 슬라이드 2 — 전체 아키텍처

```
사용자 (브라우저)
     │
     ▼
[Vercel] React 프론트엔드
     │  HTTP + X-API-Key
     ▼
[Railway] FastAPI 백엔드
     │
     ├─── [Supabase] PostgreSQL DB
     │         강의 / 강사 / 시험 / 리뷰 데이터
     │
     ├─── [OpenAI GPT] AI 추천 엔진
     │         로드맵 설계 + 강의 선별
     │
     └─── [Zapier] 이메일 발송
               추천 결과 HTML 이메일
```

---

## 슬라이드 3 — 백엔드 구조 (FastAPI)

**라우터 6개**

| 엔드포인트 | 역할 |
|---|---|
| `POST /api/recommend` | AI 로드맵 설계 + 강의 선별 |
| `POST /api/recommend/email` | 추천 결과 이메일 발송 |
| `GET /api/lectures` | 강의 검색/조회 |
| `GET /api/exams` | 자격증 시험 일정 조회 |
| `GET /api/instructors` | 강사 신뢰도 조회 |
| `POST /api/zapier/webhook` | Zapier D-Day 알림 수신 |

**보안**: 모든 요청에 `X-API-Key` 헤더 검증

---

## 슬라이드 4 — AI 추천 흐름

```
① 사용자 자연어 질문
       │
       ▼
② GPT — 로드맵 설계
   · 사용자 수준 파악 (초급/중급/고급)
   · 3~5단계 학습 경로 생성
   · 관련 자격증 추천
       │
       ▼
③ Supabase — 단계별 강의 검색
   · 각 단계 키워드로 DB 조회
   · 유튜브 보조 영상 별도 검색
       │
       ▼
④ GPT — 강의 선별 (Rerank)
   · 단계별 최적 강의 2~3개 선택
   · reason / pros / diff / fit_score / caution 생성
       │
       ▼
⑤ 사용자에게 결과 반환
```

---

## 슬라이드 5 — 데이터 수집 (크롤러)

**17개 플랫폼 크롤러**

| 분류 | 플랫폼 |
|---|---|
| 국내 유료 | 인프런, 패스트캠퍼스, Class101, Coloso, Codeit, EBS, 에듀윌, 해커스, 메가스터디, 시원스쿨, 야나두, 스파르타/제로베이스 |
| 국내 무료 | 생활코딩(opentutorials), Bearyu/Publy |
| 해외 | Udemy |
| 영상 | YouTube |

- Playwright + BeautifulSoup 기반 크롤링
- 수집 데이터: 강의명, 강사, 가격, 평점, 수강생 수, 커리큘럼, 키워드
- **현재 DB**: 강의 11,920건 / 강사 2,004명

---

## 슬라이드 6 — DB 구조 (Supabase)

**테이블 4개**

```
lectures         강의 정보 (11,920건)
  id, platform, title, instructor_name
  price, rating, student_count, url
  tags[ level: / desc: / curriculum: / keyword: ]

instructors      강사 신뢰도 (2,004명)
  trust_score, positive_ratio, review_count

reviews          강의 후기
  content, sentiment, is_ad, sentiment_score

exams            자격증 시험 일정
  exam_name, exam_date, application_start, d_day
```

---

## 슬라이드 7 — 이메일 발송 (Zapier 연동)

**흐름**
```
사용자가 강의 선택
     │
     ▼
POST /api/recommend/email
     │
     ▼
HTML 이메일 생성
  · 학습 로드맵
  · 선택 강의 카드 (추천 이유 / 장점 / 차별점 / 적합도)
  · 관련 자격증 & 시험 일정
     │
     ▼
Zapier Webhook (ZAPIER_DDAY_WEBHOOK_URL)
     │
     ▼
Gmail HTML 이메일 발송
```

---

## 슬라이드 8 — 프론트엔드 구조 (React)

**페이지 구성**

| 페이지 | 내용 |
|---|---|
| 홈 (`/`) | AI 추천 검색 + 강의 목록 |
| 대시보드 (`/dashboard`) | 플랫폼별 통계 차트 |
| 시험 일정 (`/exams`) | 자격증 D-Day 캘린더 |
| 강사 (`/instructor`) | 강사 신뢰도 조회 |
| 비교 (`/compare`) | 강의 비교 |

**주요 컴포넌트**
- `RecommendSection` — 자연어 검색 + AI 추천 결과 표시
- `LectureDetailModal` — 강의 상세 정보 팝업 (추천 이유 / 장점 / 차별점)

---

## 슬라이드 9 — 배포 구조

```
GitHub (seusik1122/2026_ai_service_project)
     │
     ├── push → Vercel 자동 배포
     │           frontend/
     │           https://2026-ai-service-project.vercel.app
     │
     └── push → Railway 자동 배포
                 backend/
                 https://2026aiserviceproject-production.up.railway.app
```

**기술 스택 요약**

| | 기술 |
|---|---|
| 프론트엔드 | React 18, TypeScript, Tailwind CSS, Vite |
| 백엔드 | Python 3.10, FastAPI, Uvicorn |
| AI | OpenAI GPT |
| DB | Supabase (PostgreSQL) |
| 크롤링 | Playwright, BeautifulSoup |
| 배포 | Vercel + Railway |
| 이메일 | Zapier Webhook → Gmail |
