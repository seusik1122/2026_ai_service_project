# 국내 강의 통합 추천 시스템 — Claude Code 전역 규칙

## 프로젝트 구조
```
ai_service/
├── backend/                        ← B담당: FastAPI 서버
│   ├── app/
│   │   ├── api/                    ← FastAPI 라우터
│   │   ├── ai/                     ← OpenAI 처리 (ad_filter, sentiment, trust_score)
│   │   ├── db/                     ← Supabase 클라이언트 + 모델 + 쿼리
│   │   ├── crawlers/               ← A담당: 플랫폼 크롤러
│   │   ├── collectors/             ← A담당: 외부 API 수집기
│   │   └── scheduler/              ← A담당: cron 스케줄러
│   ├── scripts/                    ← 일회성 스크립트 (seed_demo_data 등)
│   └── tests/
├── lecture-recommendation/
│   └── frontend/                   ← A담당: React 18 + TypeScript
└── tasks.md                        ← 마스터 체크리스트 (이 파일만 수정)
```

## 담당자 역할
- **A담당**: `app/crawlers/` + `app/collectors/` + `app/scheduler/` + `frontend/`
- **B담당**: `app/db/` + `app/ai/` + `app/api/` + Zapier 연동 + 전체 연동/배포

## 작업 시작 전 필수 절차
1. `/mnt/c/ai_service/tasks.md` 읽기 (이 파일만 마스터)
2. `[ ]` 상태인 본인 담당 항목 중 **첫 번째 항목만** 수행
3. 다음 항목으로 임의 진행 금지 — 완료 보고 후 사용자 확인 받기

## 작업 완료 후 필수 절차
1. Definition of Done 검증 실행
2. 검증 통과 시에만 `/mnt/c/ai_service/tasks.md`에서 `[ ]` → `[x]` 변경
3. `✅ {작업명} 완료. 다음 작업: {다음항목명}` 형식으로 보고

## Definition of Done

### 백엔드 (루트: `/mnt/c/ai_service/backend/`)
```bash
python -m pytest tests/test_db.py          # DB 레이어
python -m pytest tests/test_crawlers.py    # 크롤러
python -m pytest tests/test_collectors.py  # API 수집기
python -m pytest tests/test_ai.py          # AI 처리
python -m pytest tests/test_api_integration.py  # 전체 연동 (서버 실행 후)
```
FastAPI: `uvicorn main:app --reload --port 8000` 후 `/docs` 각 엔드포인트 200 응답

### 프론트엔드 (루트: `/mnt/c/ai_service/lecture-recommendation/frontend/`)
```bash
npm run build   # 에러 없음
```
브라우저에서 렌더링 + FastAPI 연결 확인

## 자주 쓰는 명령어
```bash
# 백엔드
cd /mnt/c/ai_service/backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
python -m pytest tests/ -v

# 프론트엔드
cd /mnt/c/ai_service/lecture-recommendation/frontend
npm install && npm run dev
```

## 코딩 규칙

### Python
- 타입 힌트 필수
- 비동기 함수는 `async/await` 사용
- 에러는 `try/except + logger.error()`
- `.env` 값은 `os.getenv()`로만 접근, 하드코딩 금지

### TypeScript/React
- 함수형 컴포넌트 + hooks만 사용
- props는 `interface` 타입 정의 필수
- API 호출은 `src/api/` 함수 통해서만

## 절대 하지 말 것
- `.env` API 키를 코드에 직접 작성
- DB 스키마 임의 변경
- `queries.py` 함수 시그니처 임의 변경 (A/B 공유 인터페이스)
- 명세서에 없는 라이브러리 임의 추가
- `lecture-recommendation/tasks.md` 수정 (폐기됨 — 마스터는 `/ai_service/tasks.md`)
