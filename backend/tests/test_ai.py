"""AI 처리 테스트 — 실제 OpenAI 호출 없이 mock으로 검증."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.ad_filter import filter_ad
from app.ai.sentiment import analyze_sentiment
from app.ai.trust_score import calculate_trust_score


# ── 공통 헬퍼 ──────────────────────────────────────────────

def _mock_openai_client(payload: dict) -> MagicMock:
    """_get_client()가 반환하는 AsyncOpenAI mock 생성."""
    msg = MagicMock()
    msg.content = json.dumps(payload, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]

    create_mock = AsyncMock(return_value=resp)
    client = MagicMock()
    client.chat.completions.create = create_mock
    return client


# ── filter_ad 테스트 ────────────────────────────────────────

def test_filter_ad_returns_true_for_ad():
    client = _mock_openai_client({"is_ad": True, "reason": "협찬 표시 있음"})
    with patch("app.ai.ad_filter._get_client", return_value=client):
        result = asyncio.run(filter_ad("이 강의는 체험단으로 수강했습니다. 협찬 받았어요."))

    assert result["is_ad"] is True
    assert result["reason"] == "협찬 표시 있음"
    assert "error" not in result


def test_filter_ad_returns_false_for_genuine():
    client = _mock_openai_client({"is_ad": False, "reason": "단점 언급 있고 구체적 경험 포함"})
    with patch("app.ai.ad_filter._get_client", return_value=client):
        result = asyncio.run(filter_ad("솔직히 중반부가 좀 지루했지만 전반적으로 실무에 도움됐습니다."))

    assert result["is_ad"] is False
    assert "error" not in result


def test_filter_ad_truncates_content_to_500():
    """500자 초과 입력이 500자로 잘려서 API에 전달되는지 확인."""
    long_content = "강의 후기 " * 200  # 1200자+
    captured = {}

    async def fake_create(**kwargs):
        captured["user_content"] = kwargs["messages"][1]["content"]
        msg = MagicMock()
        msg.content = json.dumps({"is_ad": False, "reason": "ok"})
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    client = MagicMock()
    client.chat.completions.create = fake_create
    with patch("app.ai.ad_filter._get_client", return_value=client):
        asyncio.run(filter_ad(long_content))

    assert len(captured["user_content"]) <= 500


def test_filter_ad_uses_correct_model():
    """gpt-4o-mini 모델을 사용하는지 확인."""
    captured = {}

    async def fake_create(**kwargs):
        captured["model"] = kwargs["model"]
        msg = MagicMock()
        msg.content = json.dumps({"is_ad": False, "reason": "ok"})
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    client = MagicMock()
    client.chat.completions.create = fake_create
    with patch("app.ai.ad_filter._get_client", return_value=client):
        asyncio.run(filter_ad("테스트"))

    assert captured["model"] == "gpt-5.4-mini"


def test_filter_ad_returns_error_flag_on_exception():
    """API 호출 실패 시 error=True, is_ad=False 반환 (예외 전파 안 함)."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=Exception("network error"))
    with patch("app.ai.ad_filter._get_client", return_value=client):
        result = asyncio.run(filter_ad("테스트"))

    assert result["is_ad"] is False
    assert result["error"] is True
    assert "network error" in result["reason"]


def test_filter_ad_handles_missing_fields_gracefully():
    """JSON 응답에 필드가 빠져 있어도 기본값으로 처리."""
    client = _mock_openai_client({})  # is_ad, reason 둘 다 없음
    with patch("app.ai.ad_filter._get_client", return_value=client):
        result = asyncio.run(filter_ad("테스트"))

    assert result["is_ad"] is False
    assert result["reason"] == ""


# ── analyze_sentiment 테스트 ────────────────────────────────

def test_analyze_sentiment_returns_positive():
    client = _mock_openai_client({"sentiment": "positive", "score": 0.9, "keywords": ["실무", "추천", "친절"]})
    with patch("app.ai.sentiment._get_client", return_value=client):
        result = asyncio.run(analyze_sentiment("정말 도움이 많이 됐어요. 강사님이 친절하고 실무 예제가 좋았습니다."))

    assert result["sentiment"] == "positive"
    assert result["score"] == 0.9
    assert result["keywords"] == ["실무", "추천", "친절"]
    assert "error" not in result


def test_analyze_sentiment_returns_negative():
    client = _mock_openai_client({"sentiment": "negative", "score": -0.7, "keywords": ["지루함", "불친절"]})
    with patch("app.ai.sentiment._get_client", return_value=client):
        result = asyncio.run(analyze_sentiment("강의가 너무 지루하고 설명이 불친절했습니다."))

    assert result["sentiment"] == "negative"
    assert result["score"] == -0.7
    assert "error" not in result


def test_analyze_sentiment_returns_neutral():
    client = _mock_openai_client({"sentiment": "neutral", "score": 0.0, "keywords": ["보통"]})
    with patch("app.ai.sentiment._get_client", return_value=client):
        result = asyncio.run(analyze_sentiment("그냥 평범한 강의였습니다."))

    assert result["sentiment"] == "neutral"
    assert result["score"] == 0.0


def test_analyze_sentiment_uses_correct_model():
    """gpt-5.5 모델을 사용하는지 확인."""
    captured = {}

    async def fake_create(**kwargs):
        captured["model"] = kwargs["model"]
        msg = MagicMock()
        msg.content = json.dumps({"sentiment": "neutral", "score": 0.0, "keywords": []})
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    client = MagicMock()
    client.chat.completions.create = fake_create
    with patch("app.ai.sentiment._get_client", return_value=client):
        asyncio.run(analyze_sentiment("테스트"))

    assert captured["model"] == "gpt-5.5"


def test_analyze_sentiment_truncates_content_to_500():
    long_content = "강의 후기 " * 200
    captured = {}

    async def fake_create(**kwargs):
        captured["user_content"] = kwargs["messages"][1]["content"]
        msg = MagicMock()
        msg.content = json.dumps({"sentiment": "neutral", "score": 0.0, "keywords": []})
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    client = MagicMock()
    client.chat.completions.create = fake_create
    with patch("app.ai.sentiment._get_client", return_value=client):
        asyncio.run(analyze_sentiment(long_content))

    assert len(captured["user_content"]) <= 500


def test_analyze_sentiment_returns_error_flag_on_exception():
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))
    with patch("app.ai.sentiment._get_client", return_value=client):
        result = asyncio.run(analyze_sentiment("테스트"))

    assert result["sentiment"] == "neutral"
    assert result["score"] == 0.0
    assert result["keywords"] == []
    assert result["error"] is True


def test_analyze_sentiment_handles_missing_fields_gracefully():
    client = _mock_openai_client({})
    with patch("app.ai.sentiment._get_client", return_value=client):
        result = asyncio.run(analyze_sentiment("테스트"))

    assert result["sentiment"] == "neutral"
    assert result["score"] == 0.0
    assert result["keywords"] == []


# ── calculate_trust_score 테스트 ────────────────────────────

def _make_reviews(scores: list[float]) -> list[dict]:
    """sentiment_score 목록으로 reviews mock 데이터 생성."""
    return [{"sentiment_score": s} for s in scores]


def test_calculate_trust_score_all_positive():
    """후기 전부 긍정(score>0), 100건 → 최고점 근사."""
    reviews = _make_reviews([0.9] * 100)
    with patch("app.ai.trust_score.get_reviews_by_instructor", return_value=reviews), \
         patch("app.ai.trust_score.update_instructor_trust_score") as mock_update:
        score = calculate_trust_score("홍길동")

    # (100/100)*60 + (0.9+1)/2*30 + min(100/100,1)*10 = 60 + 28.5 + 10 = 98.5
    assert score == 98.5
    mock_update.assert_called_once()


def test_calculate_trust_score_all_negative():
    """후기 전부 부정(score<0)."""
    reviews = _make_reviews([-0.8] * 50)
    with patch("app.ai.trust_score.get_reviews_by_instructor", return_value=reviews), \
         patch("app.ai.trust_score.update_instructor_trust_score"):
        score = calculate_trust_score("홍길동")

    # (0/50)*60 + (-0.8+1)/2*30 + min(50/100,1)*10 = 0 + 3.0 + 5.0 = 8.0
    assert score == 8.0


def test_calculate_trust_score_mixed():
    """긍정 7, 부정 3 혼합."""
    reviews = _make_reviews([0.8] * 7 + [-0.5] * 3)
    with patch("app.ai.trust_score.get_reviews_by_instructor", return_value=reviews), \
         patch("app.ai.trust_score.update_instructor_trust_score"):
        score = calculate_trust_score("홍길동")

    avg = (0.8 * 7 + (-0.5) * 3) / 10  # 0.41
    expected = round((7 / 10) * 60 + (avg + 1) / 2 * 30 + min(10 / 100, 1.0) * 10, 2)
    assert score == expected


def test_calculate_trust_score_no_reviews_returns_zero():
    """후기 없으면 0.0 반환, DB 업데이트 호출 안 함."""
    with patch("app.ai.trust_score.get_reviews_by_instructor", return_value=[]), \
         patch("app.ai.trust_score.update_instructor_trust_score") as mock_update:
        score = calculate_trust_score("홍길동")

    assert score == 0.0
    mock_update.assert_not_called()


def test_calculate_trust_score_skips_reviews_without_score():
    """sentiment_score가 None인 후기는 계산에서 제외."""
    reviews = [{"sentiment_score": 0.9}, {"sentiment_score": None}, {"sentiment_score": 0.7}]
    with patch("app.ai.trust_score.get_reviews_by_instructor", return_value=reviews), \
         patch("app.ai.trust_score.update_instructor_trust_score"):
        score = calculate_trust_score("홍길동")

    # None 제외 → 유효 후기 2건 (0.9, 0.7) 모두 양수
    avg = (0.9 + 0.7) / 2  # 0.8
    expected = round((2 / 2) * 60 + (avg + 1) / 2 * 30 + min(2 / 100, 1.0) * 10, 2)
    assert score == expected


def test_calculate_trust_score_db_error_still_returns_score():
    """DB 업데이트 실패해도 계산된 점수는 반환."""
    reviews = _make_reviews([0.5] * 10)
    with patch("app.ai.trust_score.get_reviews_by_instructor", return_value=reviews), \
         patch("app.ai.trust_score.update_instructor_trust_score", side_effect=Exception("db error")):
        score = calculate_trust_score("홍길동")

    assert score > 0
