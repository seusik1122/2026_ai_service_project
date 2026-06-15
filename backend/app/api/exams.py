import json
import os
from typing import Optional

from fastapi import APIRouter
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.db.queries import get_exams
from app.utils.logger import logger

router = APIRouter()

_EXAM_RECOMMEND_SYSTEM = """\
너는 국내 자격증 추천 전문가야.
사용자의 질문과 현재 DB에 있는 자격증 후보 목록을 받아, 아래 JSON 형태로만 응답해.

{
  "recommended": [
    {
      "exam_name": "자격증명 (후보 목록에 있는 이름과 동일하게)",
      "reason": "이 자격증이 적합한 이유 (2~3문장)",
      "difficulty": "하 | 중 | 상",
      "use_case": "취득 후 활용 분야 한 줄"
    }
  ],
  "summary": "전체 추천 이유 한 줄 요약"
}

규칙:
- recommended는 정확히 3개 (후보가 3개 미만이면 있는 것만)
- 후보 목록에 없는 자격증은 절대 추천하지 않음
- exam_name은 후보 목록의 이름과 완전히 동일해야 함
- JSON만 응답, 설명 금지
"""


class ExamRecommendRequest(BaseModel):
    question: str
    keywords: Optional[list[str]] = None


class RecommendedExam(BaseModel):
    exam_name: str
    reason: str
    difficulty: str
    use_case: str
    nearest_exam: Optional[dict] = None


class ExamRecommendResponse(BaseModel):
    question: str
    recommended_exams: list[RecommendedExam]
    summary: str


def _get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _filter_candidates(question: str, keywords: list[str]) -> list[dict]:
    all_exams = get_exams()
    if not all_exams:
        return []

    search_terms = set(kw.lower() for kw in keywords)
    for word in question.lower().split():
        if len(word) >= 2:
            search_terms.add(word)

    scored: list[tuple[int, dict]] = []
    seen_names: set[str] = set()

    for exam in all_exams:
        name = exam.get("exam_name", "")
        if name in seen_names:
            continue

        related = [kw.lower() for kw in (exam.get("related_keywords") or [])]
        name_lower = name.lower()

        score = 0
        for term in search_terms:
            if term in name_lower:
                score += 3
            for rk in related:
                if term in rk or rk in term:
                    score += 1

        if score > 0:
            seen_names.add(name)
            scored.append((score, exam))

    scored.sort(key=lambda x: x[0], reverse=True)

    if len(scored) < 5:
        for exam in all_exams:
            name = exam.get("exam_name", "")
            if name not in seen_names:
                seen_names.add(name)
                scored.append((0, exam))
            if len(scored) >= 20:
                break

    return [e for _, e in scored[:20]]


def _get_nearest_exam(exam_name: str, all_exams: list[dict]) -> Optional[dict]:
    from datetime import date
    today = date.today()
    candidates = [
        e for e in all_exams
        if e.get("exam_name") == exam_name and e.get("exam_date")
    ]
    future = [e for e in candidates if e.get("d_day") is not None and e["d_day"] >= 0]
    if future:
        return min(future, key=lambda x: x["d_day"])
    if candidates:
        return candidates[0]
    return None


@router.get("/exams")
async def search_exams(
    keyword: Optional[str] = None,
    d_day_within: Optional[int] = None,
):
    exams = get_exams(keyword=keyword, d_day_within=d_day_within)
    return {"exams": exams}


@router.post("/exams/recommend", response_model=ExamRecommendResponse)
async def recommend_exams(body: ExamRecommendRequest):
    keywords = body.keywords or []
    candidates = _filter_candidates(body.question, keywords)
    all_exams = get_exams()

    candidate_names = list(dict.fromkeys(e["exam_name"] for e in candidates))
    candidate_list_str = "\n".join(f"- {name}" for name in candidate_names)

    user_msg = f"질문: {body.question}\n\n추천 후보 자격증 목록:\n{candidate_list_str}"

    client = _get_openai_client()
    try:
        resp = await client.chat.completions.create(
            model="gpt-5.5",
            messages=[
                {"role": "system", "content": _EXAM_RECOMMEND_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=600,
        )
        parsed = json.loads(resp.choices[0].message.content)
    except Exception as e:
        logger.error(f"자격증 추천 GPT 호출 실패: {e}")
        return ExamRecommendResponse(
            question=body.question,
            recommended_exams=[],
            summary="추천 서비스를 일시적으로 사용할 수 없습니다.",
        )

    recommended_exams: list[RecommendedExam] = []
    for item in parsed.get("recommended", []):
        name = item.get("exam_name", "")
        nearest = _get_nearest_exam(name, all_exams)
        recommended_exams.append(RecommendedExam(
            exam_name=name,
            reason=item.get("reason", ""),
            difficulty=item.get("difficulty", "중"),
            use_case=item.get("use_case", ""),
            nearest_exam=nearest,
        ))

    return ExamRecommendResponse(
        question=body.question,
        recommended_exams=recommended_exams,
        summary=parsed.get("summary", ""),
    )
