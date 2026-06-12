# lecture-recommendation — A담당 프론트엔드 규칙

> 전역 규칙: `/mnt/c/ai_service/CLAUDE.md` 참조
> 마스터 체크리스트: `/mnt/c/ai_service/tasks.md` (이 폴더의 tasks.md는 폐기)

## 이 폴더의 역할
- 문서 전용 폴더 (명세서, 계획서, 작업 히스토리)
- 실제 코드는 모두 `/mnt/c/ai_service/` 로 통합됨

| 코드 위치 | 경로 |
|----------|------|
| 백엔드 | `/mnt/c/ai_service/backend/` |
| 프론트엔드 | `/mnt/c/ai_service/frontend/` |
| 마스터 tasks | `/mnt/c/ai_service/tasks.md` |

## 코딩 규칙

### TypeScript/React
- 함수형 컴포넌트 + hooks만 사용 (class 금지)
- props는 `interface`로 컴포넌트 바로 위에 정의
- 스타일은 Tailwind CSS
- API 호출은 `src/api/` 함수 통해서만 (컴포넌트에서 직접 axios 금지)

### 상태 관리
- 서버 상태: TanStack Query (`useQuery`, `useMutation`)
- 로컬 상태: `useState`, `useReducer`

### 파일 위치
- 페이지: `src/pages/`
- 컴포넌트: `src/components/`
- API 함수: `src/api/`
- 타입: `src/types/`
- 훅: `src/hooks/`

## 절대 하지 말 것
- `.env` API 키를 코드에 직접 작성
- `queries.py` 함수 시그니처 임의 변경
- 명세서에 없는 라이브러리 임의 추가
- 이 폴더의 `tasks.md` 수정 (마스터는 `/ai_service/tasks.md`)
