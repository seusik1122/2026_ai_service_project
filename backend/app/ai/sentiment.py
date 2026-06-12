import json
import os
from functools import lru_cache

from openai import AsyncOpenAI
from app.utils.logger import logger

_SYSTEM_PROMPT = (
    "강의 후기 텍스트를 분석해서 감성을 판단해.\n"
    "반드시 JSON으로만 응답:\n"
    "{\n"
    "  \"sentiment\": \"positive\" | \"negative\" | \"neutral\",\n"
    "  \"score\": -1.0 ~ 1.0,\n"
    "  \"keywords\": [\"핵심 키워드 최대 3개\"]\n"
    "}"
)


@lru_cache(maxsize=1)
def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def analyze_sentiment(content: str) -> dict:
    """후기 텍스트 감성 분석.

    반환: {"sentiment": str, "score": float, "keywords": list}
    실패 시: {"sentiment": "neutral", "score": 0.0, "keywords": [], "error": True}
    """
    try:
        response = await _get_client().chat.completions.create(
            model="gpt-5.5",
            max_completion_tokens=150,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": content[:500]},
            ],
        )
        result = json.loads(response.choices[0].message.content)
        return {
            "sentiment": result.get("sentiment", "neutral"),
            "score": float(result.get("score", 0.0)),
            "keywords": result.get("keywords", []),
        }
    except Exception as e:
        logger.error(f"감성 분석 실패 — {e}")
        return {"sentiment": "neutral", "score": 0.0, "keywords": [], "error": True}
