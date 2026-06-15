import json
import os
from functools import lru_cache

from openai import AsyncOpenAI
from app.utils.logger import logger

_SYSTEM_PROMPT = (
    "너는 블로그 후기가 광고성인지 진짜 수강 후기인지 판별하는 전문가야.\n"
    "아래 기준으로 판단해:\n"
    "- 광고: '협찬', '소정의 원고료', '체험단', 과도한 긍정만 있고 단점 없음, 특정 링크 삽입\n"
    "- 진짜: 구체적 수강 경험, 단점 언급, 비교 내용 포함\n"
    "반드시 JSON으로만 응답: {\"is_ad\": true/false, \"reason\": \"판단 이유 한 줄\"}"
)


@lru_cache(maxsize=1)
def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def filter_ad(content: str) -> dict:
    """후기 텍스트가 광고성인지 판별.

    반환: {"is_ad": bool, "reason": str}
    실패 시: {"is_ad": False, "reason": "...", "error": True}
    """
    try:
        response = await _get_client().chat.completions.create(
            model="gpt-5.5",
            max_completion_tokens=100,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": content[:500]},
            ],
        )
        result = json.loads(response.choices[0].message.content)
        return {
            "is_ad": bool(result.get("is_ad", False)),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.error(f"광고 필터링 실패 — {e}")
        return {"is_ad": False, "reason": str(e), "error": True}
