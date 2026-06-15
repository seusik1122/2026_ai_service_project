# 작업 체크리스트 (현재 진행 중 항목만)

> 규칙: 작업 완료 시 [ ] → [x] 즉시 변경. 한 번에 한 항목만 진행.
> 마스터 체크리스트: 이 파일만 수정. `lecture-recommendation/tasks.md`는 폐기됨.

---

## 현재 완료된 기반 상태

- DB: Supabase lectures(11,920건) / instructors(2,004명) / reviews(32건) / exams(6건)
- 백엔드: FastAPI + 크롤러 17개 + POST /api/recommend (GPT-4o-mini 쿼리 파싱)
- 프론트엔드: React + HomePage에 RecommendSection (자연어 검색 UI) 통합 완료
- Zapier: .env에 웹훅 URL 4개 저장됨 (실제 POST 발송은 미구현)

---

## 🔧 Phase 1 — 검색 품질 개선 ✅ 완료

> 문제: 키워드가 제목에 없으면 0건 (예: "기초 일러스트" → "그림 그리기" 강의 누락)

- [x] `search_lectures_multi()` OR 검색으로 변경 — postgrest `or_()` 단일 쿼리 방식
- [x] 유사어 매핑 테이블 추가 — `SYNONYM_MAP` (일러스트→드로잉/그림, 파이썬→Python 등)
- [x] category 매핑 완화 — `CATEGORY_MAP` (GPT "AI/머신러닝" → DB ["AI/머신러닝","AI활용","데이터사이언스","IT/개발"])
- [x] tags 컬럼 검색: text[] 배열이라 직접 ilike 불가 → 키워드 확장(SYNONYM_MAP)으로 커버

---

## 🎴 Phase 2 — 강의 상세 모달 (클릭 시 AI 분석) ✅ 완료

- [x] `GET /api/lectures/{id}/detail` — 강의 + 강사 신뢰도 + 후기 3건
- [x] `POST /api/lectures/{id}/why` — GPT 추천 이유 2~3줄 생성
- [x] `LectureDetailModal.tsx` — AI 추천 이유 / 신뢰도 게이지 / 후기 / 원본 링크
- [x] `LectureCard.tsx` 클릭 이벤트 + `LectureList` 모달 상태 관리

---

## 📅 자격증 시험 일정 수집 ✅ 완료

- [x] `app/collectors/exam_crawler.py` 구현
  - 큐넷 42종 + 정적소스 19종 = **61종, 86건** DB 저장
  - 전기/IT/조리/미용/환경/안전/금융/어학/디자인/데이터 전 분야 커버
  - TOEIC 정기시험 6회차, AWS/GCP/Azure 클라우드, SQLD/SQLP, ADsP/ADP 등 포함
  - 강의 카테고리 → 관련 자격증 매핑 (`CATEGORY_EXAM_MAP`) 대폭 확장
- [x] `POST /api/exams/recommend` — GPT가 키워드 기반 자격증 3개 추천 + 이유/난이도/활용분야 + 가장 가까운 시험일정 반환

## 🔔 Phase 3 — Zapier 연동 (구글 캘린더 + 이메일) ✅ 완료

- [x] `ZAPIER_DDAY_WEBHOOK_URL` — D-day 이메일
  - D-7 이하 시험 감지 → 시험명 + 접수마감 + 관련 강의 TOP3 포함 이메일
  - 실제 전송 확인 (2건 발송 성공)
- [x] `ZAPIER_NEW_LECTURE_WEBHOOK_URL` — 구글 캘린더 시험 일정 자동 등록
  - `collect_all_exams()` 저장 직후 → 시험일 + 접수마감 캘린더 이벤트 자동 생성
- [x] `ZAPIER_TRUST_SCORE_WEBHOOK_URL` — 주간 신뢰도 급변 이메일
  - ±10점 이상 변동 강사 → 후기 원문 2건 포함 이메일
- [x] 스케줄러 자동 트리거: 매일 00:05 D-day 알림 / 매주 월 09:00 신뢰도 알림
- [x] 수동 트리거 API: `POST /api/zapier/dday`, `POST /api/zapier/trust`

---

## 🧪 Phase 4 — 발표 시나리오 최종 검증

> 시나리오: 자연어 검색 → 강의 클릭 → AI 추천 이유 확인 → 강사 신뢰도 확인 → D-day 알림 확인

- [ ] 시나리오 1: "토익 무료 강의" 입력 → 유튜브/해커스 강의 5건 이상 추천 확인
- [ ] 시나리오 2: "기초 일러스트 강의" 입력 → 콜로소/클래스101 강의 추천 확인 (유사어 매핑 검증)
- [ ] 시나리오 3: 강의 카드 클릭 → 모달에서 AI 추천 이유 + 강사 신뢰도 표시 확인
- [ ] 시나리오 4: ExamPage에서 D-day 배지 표시 확인 (토익 D-8 등)
- [ ] 시나리오 5: Zapier 웹훅 수신 로그 확인
- [ ] `npm run build` 에러 없음 최종 확인
