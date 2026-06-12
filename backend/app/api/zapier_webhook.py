import os
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from app.db.queries import log_zapier_alert
from app.utils.logger import logger

router = APIRouter()

WEBHOOK_MAP = {
    "dday_alert":   "ZAPIER_DDAY_WEBHOOK_URL",
    "new_lecture":  "ZAPIER_NEW_LECTURE_WEBHOOK_URL",
    "review_spike": "ZAPIER_TRUST_SCORE_WEBHOOK_URL",
    "form_to_db":   "ZAPIER_FORM_TO_DB_WEBHOOK_URL",
}


class ZapierTriggerRequest(BaseModel):
    event_type: str
    data: dict


@router.post("/zapier/trigger")
async def zapier_trigger(body: ZapierTriggerRequest):
    """Zapier 웹훅 트리거 + 알림 이력 저장.

    event_type: "dday_alert" | "new_lecture" | "review_spike"
    """
    env_key = WEBHOOK_MAP.get(body.event_type)
    webhook_url = os.getenv(env_key) if env_key else None

    if webhook_url:
        payload = dict(body.data)
        # Gmail "To" 필드가 비지 않도록 email 기본값 보장
        if body.event_type == "form_to_db" and not payload.get("email"):
            payload["email"] = os.getenv("ADMIN_EMAIL", "kkhlhj485@gmail.com")
        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json=payload, timeout=10)
            logger.info(f"Zapier 웹훅 전송: {body.event_type}")
        except Exception as e:
            logger.error(f"Zapier 웹훅 실패: {body.event_type} — {e}")

    log_zapier_alert(body.event_type, body.data)
    return {"status": "ok", "event_type": body.event_type}
