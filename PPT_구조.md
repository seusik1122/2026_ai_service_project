# 국내 강의 통합 추천 시스템 — PPT 구성안

> 이 문서를 바탕으로 PPT를 제작해주세요.
> 슬라이드 총 10장, 각 슬라이드마다 제목 / 핵심 내용 / 시각화 요소를 포함합니다.

---

## 슬라이드 1 — 서비스 소개

**제목**: 국내 강의 통합 추천 시스템

**핵심 한 줄**: "자연어로 질문하면 AI가 학습 로드맵과 맞춤 강의를 추천해드립니다"

**주요 수치 (강조 박스 3개)**
- 📚 통합 강의 수: **11,920건**
- 🏢 연동 플랫폼: **17개**
- 👨‍🏫 등록 강사: **2,004명**

**서비스 접속 주소**
- 🌐 https://2026-ai-service-project.vercel.app

---

## 슬라이드 2 — 전체 시스템 아키텍처

**제목**: 전체 아키텍처

**다이어그램 (좌→우 흐름)**

```
[사용자 브라우저]
       │
       │ HTTPS + X-API-Key 인증
       ▼
[Vercel] React 18 프론트엔드
  · TypeScript + Tailwind CSS
  · 자연어 검색 UI
  · 강의 카드 / 로드맵 / 모달
       │
       │ REST API 호출
       ▼
[Railway] FastAPI 백엔드 (Python 3.10)
  · API 키 미들웨어로 모든 요청 보호
  · 6개 라우터 (lectures / recommend / exams / instructors / reviews / zapier)
       │
       ├──────────────────────────────────┐
       ▼                                  ▼
[Supabase]                         [OpenAI GPT]
PostgreSQL DB                      AI 추천 엔진
· lectures 11,920건                · 로드맵 설계
· instructors 2,004명              · 강의 선별 (Rerank)
· exams (자격증 일정)              · 자격증 추천
· reviews (후기)
       │
       ▼
[Zapier Webhook]
이메일 자동 발송
· HTML 이메일 생성
· Gmail로 최종 전달
```

---

## 슬라이드 3 — 백엔드 API 구조

**제목**: FastAPI 백엔드 — 라우터 구조

**설명**
모든 API 요청은 `X-API-Key` 헤더 검증을 거쳐야 합니다. `/health`, `/docs` 등 공개 경로만 예외입니다.

**라우터 테이블**

| 메서드 | 엔드포인트 | 역할 | 핵심 동작 |
|--------|-----------|------|----------|
| POST | `/api/recommend` | AI 강의 추천 | GPT 로드맵 설계 → DB 검색 → GPT 선별 |
| POST | `/api/recommend/email` | 추천 결과 이메일 발송 | HTML 이메일 생성 → Zapier 웹훅 전송 |
| GET | `/api/lectures` | 강의 검색/조회 | 키워드·플랫폼·가격·무료 필터 |
| GET | `/api/exams` | 자격증 시험 일정 | D-Day 계산 포함 |
| GET | `/api/instructors` | 강사 신뢰도 조회 | trust_score, 긍정 후기 비율 |
| POST | `/api/zapier/dday` | D-Day 알림 수신 | Zapier에서 보내는 시험 D-Day 알림 처리 |

---

## 슬라이드 4 — AI 추천 흐름 (핵심)

**제목**: AI 추천 엔진 — 3단계 파이프라인

**흐름도**

```
① 사용자 자연어 입력
   예) "토익 처음 시작하는데 돈이 없어요"
                │
                ▼
② [GPT — 로드맵 설계]
   · 사용자 수준 판단: 초급 / 중급 / 고급
   · 3~5단계 학습 경로 생성 (단계별 제목 / 설명 / 예상 기간)
   · 각 단계별 DB 검색 키워드 추출
   · 관련 자격증 추천 (시험명 / 준비 기간 / 난이도)
   · 유튜브 후기·공부법 검색어 생성
   출력 예) 1단계: 토익 기초문법(2주) → 2단계: LC 집중(4주) → ...
                │
                ▼
③ [Supabase DB — 단계별 강의 검색]
   · 각 단계 키워드로 OR 검색 (최대 15건/단계)
   · 유튜브 보조 영상 별도 검색 (최대 4건)
   · 플랫폼 쏠림 방지: 유튜브 최대 10건 + 나머지 플랫폼 50건 합산
                │
                ▼
④ [GPT — 강의 선별 (Rerank)]
   · 단계별 최적 강의 2~3개 선택
   · 각 강의마다 5가지 분석 생성:
     - reason   : 이 단계에 적합한 이유 (2~3문장)
     - pros     : 핵심 장점 3가지 (배열)
     - diff     : 같은 단계 다른 강의와의 차별점
     - fit_score: 단계 목표 적합도 1~10점
     - caution  : 주의사항 또는 단점
                │
                ▼
⑤ 사용자에게 결과 반환
   · 로드맵 카드 + 단계별 강의 카드
   · 강의 클릭 시 상세 모달 (reason / pros / diff / caution 표시)
   · 원하는 강의 선택 후 이메일로 받기
```

---

## 슬라이드 5 — 데이터 수집 구조 (크롤러)

**제목**: 17개 플랫폼 크롤러

**수집 방식**
- Playwright (헤드리스 브라우저) + BeautifulSoup 파싱
- URL 기준 upsert로 중복 방지
- 수집 항목: 강의명, 강사, 가격, 평점, 수강생 수, 썸네일, URL

**플랫폼 분류표**

| 분류 | 플랫폼 | 특징 |
|------|--------|------|
| IT/개발 | 인프런, Codeit, 스파르타코딩, 제로베이스 | 국내 개발 특화 |
| 종합 | 패스트캠퍼스, Class101, Coloso | 다양한 분야 |
| 어학 | 해커스, 시원스쿨, 야나두 | 토익/영어 특화 |
| 수능/자격증 | 메가스터디, EBS, 에듀윌 | 시험 대비 |
| 무료 | 생활코딩(opentutorials), Bearyu/Publy | 무료 강의 |
| 해외 | Udemy | 영어 강의 |
| 영상 | YouTube | 후기·공부법 영상 |

**데이터 보강 (enrich)**
- 강의 설명·키워드 부족한 경우: 유튜브 댓글 + 구글 검색 결과 수집
- GPT로 요약 후 `tags` 배열에 저장 (`desc:` / `level:` / `curriculum:` / `keyword:` 접두사 구조)

---

## 슬라이드 6 — DB 구조 (Supabase)

**제목**: 데이터베이스 구조 — Supabase (PostgreSQL)

**테이블 상세**

**① lectures** (강의 — 11,920건)
```
id               정수 PK
platform         플랫폼명 (inflearn, youtube, hackers ...)
title            강의 제목
instructor_name  강사명
price            가격 (원, 0이면 무료)
is_free          무료 여부
rating           평점 (0~5)
student_count    수강생 수
url              강의 원본 URL (UNIQUE — upsert 기준)
thumbnail_url    썸네일 이미지
tags             구조화 태그 배열
                 예) ["level:초급", "desc:이 강의는...",
                      "curriculum:1강 소개...", "keyword:파이썬"]
```

**② instructors** (강사 — 2,004명)
```
instructor_name  강사명 (UNIQUE)
trust_score      신뢰도 점수 (0~100)
positive_ratio   긍정 후기 비율
review_count     분석된 후기 수
last_calculated  마지막 계산 일시
```

**③ exams** (자격증 시험 일정)
```
exam_name        시험명 (예: 토익, 정보처리기사)
exam_type        유형 (필기/실기)
application_start  접수 시작일
application_end    접수 마감일
exam_date        시험일
result_date      결과 발표일
d_day            시험까지 남은 일수 (매일 자동 갱신)
related_keywords 관련 키워드 배열
```

**④ reviews** (강의 후기)
```
instructor_name  강사명
platform_source  수집 출처
content          후기 내용
is_ad            광고성 여부 (GPT 판별)
sentiment        감성 (positive/negative/neutral)
sentiment_score  감성 점수
```

---

## 슬라이드 7 — 이메일 발송 흐름 (Zapier 연동)

**제목**: 추천 결과 이메일 — Zapier 웹훅 연동

**흐름**

```
① 사용자가 원하는 강의 선택
              │
              ▼
② POST /api/recommend/email 호출
   전달 데이터:
   · question  : 원래 질문
   · roadmap   : AI가 설계한 학습 로드맵
   · lectures  : 선택한 강의 목록
   · certs     : GPT 추천 자격증 목록
              │
              ▼
③ 백엔드에서 HTML 이메일 생성
   이메일 구성:
   · 헤더        : 인디고 그라데이션 + 질문 텍스트
   · 목표 요약   : 수준 배지(초급/중급/고급) + 목표
   · 학습 로드맵 : 단계별 카드 (번호 원 + 설명 + 기간)
   · 선택 강의   : 플랫폼·가격 배지 / 추천 이유 / 핵심 장점 /
                   차별점 / 적합도 바 / 커리큘럼 / 주의사항 / 키워드 태그
   · 자격증 일정 : 관련 자격증 + DB에서 조회한 실제 시험 일정 + D-Day
   · 유튜브 영상 : 후기·공부법 영상 링크
              │
              ▼
④ Zapier Webhook (ZAPIER_DDAY_WEBHOOK_URL) 호출
   전송 데이터: { to, subject, body(HTML), html_body }
              │
              ▼
⑤ Zapier → Gmail HTML 이메일 발송
```

---

## 슬라이드 8 — 프론트엔드 구조 (React)

**제목**: 프론트엔드 — React 18 + TypeScript

**페이지 구성**

| 경로 | 페이지 | 주요 기능 |
|------|--------|----------|
| `/` | 홈 | AI 추천 검색창 + 강의 목록 + 필터 |
| `/dashboard` | 대시보드 | 플랫폼별 통계 차트 (Recharts) |
| `/exams` | 시험 일정 | 자격증 D-Day 캘린더 |
| `/instructor` | 강사 | 강사 신뢰도 조회 |
| `/compare` | 강의 비교 | 강의 나란히 비교 |

**핵심 컴포넌트**

```
RecommendSection (홈 핵심 컴포넌트)
  · 자연어 입력창 + 예시 질문 버튼
  · AI 추천 결과: 로드맵 카드 + 단계별 강의 그룹
  · 강의 카드 클릭 → LectureDetailModal 오픈
  · 강의 선택 → 이메일 입력 → 발송

LectureDetailModal (강의 상세 팝업)
  · 추천 이유 / 핵심 장점 3가지 / 차별점
  · 적합도 점수 / 커리큘럼 / 주의사항 / 키워드 태그
  · 강의 바로가기 버튼
```

**API 통신 구조**
- `src/api/` 폴더에 기능별 함수 분리 (lectures / recommend / exams / instructors)
- axios + `X-API-Key` 헤더 자동 주입 (interceptor)
- `@tanstack/react-query` 로 캐싱·로딩 상태 관리

---

## 슬라이드 9 — 배포 구조

**제목**: 배포 — GitHub → Vercel + Railway 자동 배포

**다이어그램**

```
개발자 (로컬)
     │
     │ git push
     ▼
GitHub
seusik1122/2026_ai_service_project
     │
     ├── frontend/ 변경 감지
     │        │
     │        ▼
     │   [Vercel] 자동 빌드 + 배포
     │   · npm run build (Vite)
     │   · 정적 파일 CDN 배포
     │   · https://2026-ai-service-project.vercel.app
     │
     └── backend/ 변경 감지
              │
              ▼
         [Railway] Docker 빌드 + 배포
         · Dockerfile 기반 이미지 빌드
           (Playwright + Python 패키지 포함)
         · uvicorn 실행 (PORT 환경변수 자동 적용)
         · https://2026aiserviceproject-production.up.railway.app
```

**환경변수 관리**

| 위치 | 변수 | 용도 |
|------|------|------|
| Railway | `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | DB 접속 |
| Railway | `OPENAI_API_KEY` | GPT 호출 |
| Railway | `ZAPIER_DDAY_WEBHOOK_URL` | 이메일 발송 |
| Railway | `API_SECRET_KEY` | API 인증 키 |
| Vercel | `VITE_API_URL` | 백엔드 주소 |
| Vercel | `VITE_INTERNAL_API_KEY` | API 인증 키 |

---

## 슬라이드 10 — 기술 스택 요약

**제목**: 기술 스택 전체 요약

**표**

| 영역 | 기술 | 역할 |
|------|------|------|
| 프론트엔드 | React 18 + TypeScript | UI 구성 |
| 스타일 | Tailwind CSS | 디자인 |
| 빌드 | Vite | 번들링 |
| 차트 | Recharts | 통계 시각화 |
| 상태관리 | TanStack Query | 서버 상태 캐싱 |
| 백엔드 | FastAPI (Python 3.10) | REST API 서버 |
| 크롤링 | Playwright + BeautifulSoup | 강의 데이터 수집 |
| AI | OpenAI GPT | 로드맵 설계 + 강의 선별 |
| DB | Supabase (PostgreSQL) | 데이터 저장·조회 |
| 이메일 | Zapier Webhook → Gmail | HTML 이메일 발송 |
| 배포 (FE) | Vercel | 프론트엔드 호스팅 |
| 배포 (BE) | Railway + Docker | 백엔드 컨테이너 배포 |
| 형상관리 | GitHub | 코드 버전 관리 + 자동 배포 트리거 |
