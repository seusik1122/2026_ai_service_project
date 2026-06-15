import os
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from app.db.queries import log_zapier_alert, get_exams, search_lectures_multi, get_instructors_with_score_change
from app.db.supabase_client import supabase
from app.utils.logger import logger

router = APIRouter()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "kkhlhj485@gmail.com")

WEBHOOK_URLS = {
    "dday_alert":        "ZAPIER_DDAY_WEBHOOK_URL",
    "calendar_exam":     "ZAPIER_NEW_LECTURE_WEBHOOK_URL",
    "trust_score_alert": "ZAPIER_TRUST_SCORE_WEBHOOK_URL",
}


async def _post(event_type: str, payload: dict) -> None:
    env_key = WEBHOOK_URLS.get(event_type)
    url = os.getenv(env_key) if env_key else None
    if not url:
        logger.warning(f"Zapier URL 미설정: {event_type}")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
        logger.info(f"Zapier 전송 완료: {event_type}")
    except Exception as e:
        logger.error(f"Zapier 전송 실패: {event_type} — {e}")
    log_zapier_alert(event_type, payload)


# ── D-day 이메일 트리거 ────────────────────────────────────

async def trigger_dday_alerts() -> int:
    """D-7 이하 시험 감지 → 관련 강의 TOP3 포함 이메일 Zapier 전송."""
    exams = get_exams(d_day_within=7)
    sent = 0

    for exam in exams:
        if exam.get("d_day") is None or exam["d_day"] < 0:
            continue

        # related_keywords 기반 관련 강의 TOP3
        keywords: list[str] = exam.get("related_keywords") or [exam["exam_name"]]
        lectures = search_lectures_multi(
            keywords=keywords[:3],
            sort="rating",
            limit=3,
        )

        lecture_lines = []
        for lec in lectures:
            price = "무료" if lec.get("is_free") else f"{lec.get('price', 0):,}원"
            lecture_lines.append(
                f"• {lec['title']} ({lec['platform']}) — {price}"
            )

        payload = {
            "to": ADMIN_EMAIL,
            "subject": f"[D-{exam['d_day']}] {exam['exam_name']} {exam['exam_type']} 시험 임박",
            "exam_name": exam["exam_name"],
            "exam_type": exam["exam_type"],
            "exam_date": exam.get("exam_date", ""),
            "application_end": exam.get("application_end", ""),
            "d_day": exam["d_day"],
            "related_lectures": "\n".join(lecture_lines) if lecture_lines else "관련 강의 없음",
            "body": (
                f"📅 {exam['exam_name']} {exam['exam_type']} 시험이 D-{exam['d_day']}입니다.\n\n"
                f"시험일: {exam.get('exam_date', '미정')}\n"
                f"접수 마감: {exam.get('application_end', '미정')}\n\n"
                f"📚 관련 추천 강의:\n" + "\n".join(lecture_lines or ["관련 강의 없음"])
            ),
        }

        await _post("dday_alert", payload)
        sent += 1

    return sent


# ── 구글 캘린더 시험 일정 등록 ──────────────────────────────

async def trigger_calendar_exam(exam: dict) -> None:
    """새 시험 저장 시 구글 캘린더에 이벤트 등록."""
    if not exam.get("exam_date"):
        return

    payload = {
        "title": f"{exam['exam_name']} {exam['exam_type']}",
        "date": exam["exam_date"],
        "description": (
            f"시험: {exam['exam_name']} {exam['exam_type']}\n"
            f"시험일: {exam.get('exam_date', '')}\n"
            f"접수 마감: {exam.get('application_end', '미정')}\n"
            f"결과 발표: {exam.get('result_date', '미정')}"
        ),
        "all_day": True,
    }

    # 접수 마감일도 별도 이벤트로 등록
    if exam.get("application_end"):
        deadline_payload = {
            "title": f"{exam['exam_name']} {exam['exam_type']} 접수 마감",
            "date": exam["application_end"],
            "description": f"{exam['exam_name']} {exam['exam_type']} 원서 접수 마감일",
            "all_day": True,
        }
        await _post("calendar_exam", deadline_payload)

    await _post("calendar_exam", payload)


# ── 신뢰도 급변 이메일 트리거 ──────────────────────────────

async def trigger_trust_score_alerts() -> int:
    """신뢰도 ±10점 이상 변동 강사 감지 → 후기 원문 포함 이메일 전송."""
    changed = get_instructors_with_score_change(threshold=10.0)
    sent = 0

    for item in changed:
        name = item["instructor_name"]

        # 변동 원인 후기 2건 (가장 최신)
        reviews = (
            supabase.table("reviews")
            .select("content,sentiment,collected_at")
            .eq("instructor_name", name)
            .eq("is_ad", False)
            .order("collected_at", desc=True)
            .limit(2)
            .execute()
            .data
        )

        review_lines = []
        for r in reviews:
            sentiment_icon = "👍" if r.get("sentiment") == "positive" else "👎" if r.get("sentiment") == "negative" else "•"
            review_lines.append(f"{sentiment_icon} {r.get('content', '')[:100]}")

        direction_icon = "📈" if item["direction"] == "상승" else "📉"
        payload = {
            "to": ADMIN_EMAIL,
            "subject": f"[신뢰도 {item['direction']}] {name} 강사 {item['change']:+.1f}점 변동",
            "instructor_name": name,
            "current_score": item["current_score"],
            "previous_score": item["previous_score"],
            "change": item["change"],
            "direction": item["direction"],
            "recent_reviews": "\n".join(review_lines) if review_lines else "후기 없음",
            "body": (
                f"{direction_icon} {name} 강사의 신뢰도가 변동되었습니다.\n\n"
                f"이전: {item['previous_score']}점 → 현재: {item['current_score']}점 "
                f"({item['change']:+.1f}점 {item['direction']})\n\n"
                f"📝 최근 후기:\n" + "\n".join(review_lines or ["후기 없음"])
            ),
        }

        await _post("trust_score_alert", payload)
        sent += 1

    return sent


# ── 수동 트리거 API (테스트/운영용) ────────────────────────

class ZapierTriggerRequest(BaseModel):
    event_type: str
    data: dict


@router.post("/zapier/trigger")
async def zapier_trigger(body: ZapierTriggerRequest):
    """수동 Zapier 웹훅 트리거 (테스트용)."""
    await _post(body.event_type, body.data)
    return {"status": "ok", "event_type": body.event_type}


@router.post("/zapier/dday")
async def zapier_dday():
    """D-day 알림 수동 실행 (스케줄러 없이 테스트 가능)."""
    sent = await trigger_dday_alerts()
    return {"status": "ok", "sent": sent}


@router.post("/zapier/trust")
async def zapier_trust():
    """신뢰도 급변 알림 수동 실행."""
    sent = await trigger_trust_score_alerts()
    return {"status": "ok", "sent": sent}
