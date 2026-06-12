# 작업 체크리스트

> 규칙: 작업 완료 시 [ ] → [x] 즉시 변경. 한 번에 한 항목만 진행.

---

## 🅐 A담당 — 크롤러 + 외부 API + 프론트엔드

### 1주차 — 환경 세팅
- [x] Supabase 프로젝트 생성 + SQL Editor에서 DB 스키마 5개 실행
- [x] requirements.txt 설치 + playwright install chromium
- [x] .env 파일 생성 (.env.example 참고)
- [x] B가 완성한 queries.py 함수 목록 확인

### 2주차 — 크롤러 + 수집기
- [x] base_crawler.py 구현
- [x] inflearn.py 완성 + upsert_lecture() 연결 확인
- [x] class101.py 완성
- [x] fastcampus.py 완성
- [x] naver_api.py 완성 + insert_review() 연결 확인
- [x] youtube_api.py 완성
- [x] kmooc_api.py 완성
- [x] qnet_api.py 완성 + upsert_exam() 연결 확인
- [x] cron_jobs.py 스케줄러 등록
- [x] ⚠️ B 인계 — Supabase 대시보드 데이터 적재 확인 후 알림 (시연용 시드 데이터로 적재)

### 3주차 — React 기초
- [x] Vite + TypeScript 프로젝트 초기화
- [x] package.json 의존성 설치
- [x] api/client.ts Axios 설정
- [x] LectureCard, LectureList, LectureFilter 구현
- [x] HomePage, DashboardPage 레이아웃 구현

### 4주차 — React 완성
- [x] InstructorPage, ExamPage, ComparePage 구현
- [x] TrustTrendChart, PlatformCompareChart, CategoryPieChart, SentimentGauge 구현
- [x] useLectures, useInstructor, useExams 훅 구현 (TanStack Query)
- [x] B FastAPI 엔드포인트 연결 테스트
- [x] npm run build 에러 없음 확인

---

## 🅑 B담당 — DB + AI + FastAPI + Zapier + 연동

### 1주차 — DB 레이어 (A보다 먼저 완료)
- [x] FastAPI 프로젝트 구조 세팅 (섹션 2 기준)
- [x] main.py 기본 앱 + CORS 설정
- [x] db/supabase_client.py 구현 (섹션 3-1 코드 그대로)
- [x] db/models.py 구현 (섹션 3-2 코드 그대로)
- [x] db/queries.py 전체 함수 구현 (섹션 3-3 코드 그대로)
- [x] tests/test_db.py 작성 + 통과 확인 (17/17)
- [x] ⚠️ A에게 공유 — queries.py 완성 알림 (크롤러 개발 시 바로 사용 가능)
- [x] Zapier Webhook URL 4개 발급 → .env 저장

### 2주차 — AI 처리 (A 인계 후 시작)
- [x] ad_filter.py 구현 (섹션 6 프롬프트 그대로)
- [x] tests/test_ai.py 광고 필터링 테스트 + 통과
- [x] sentiment.py 구현 (섹션 6 프롬프트 그대로)
- [x] tests/test_ai.py 감성 분석 테스트 + 통과
- [x] trust_score.py 구현 (섹션 6 계산식 그대로)
- [x] A 데이터 일괄 분석 실행 (trust_score 초기값 생성)

### 3주차 — FastAPI + Zapier
- [x] api/lectures.py GET /api/lectures 완성
- [x] api/instructors.py GET /api/instructors/{name} 완성
- [x] api/reviews.py 완성
- [x] api/exams.py GET /api/exams 완성
- [x] api/zapier_webhook.py POST /api/zapier/trigger 완성
- [x] /docs 전체 엔드포인트 응답 200 확인
- [x] Zapier Zap 1번 구성 (D-day 알림)
- [x] Zapier Zap 2번 구성 (신규 강의 알림)
- [x] Zapier Zap 3번 구성 (후기 급변 알림)
- [x] Zapier Zap 4번 구성 (Google Form → DB)
- [x] Zapier Tables + Interfaces 설정

### 4주차 — 전체 연동 + 배포
- [x] FastAPI ↔ React 파이프라인 연동 테스트
- [x] Zapier ↔ FastAPI ↔ 대시보드 end-to-end 테스트
- [ ] Render 또는 Railway 배포 (Playwright headless 설정 포함)
- [ ] 시연용 더미 데이터 30건 이상 준비
- [ ] 발표 시나리오 테스트: 강의 검색 → 강사 신뢰도 → D-day 알림
