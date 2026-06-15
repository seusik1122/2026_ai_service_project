"""자연어 강의 추천 — 로드맵 설계 → 단계별 DB 검색 → GPT 선별."""
import json
import os
import re
from functools import lru_cache

from openai import AsyncOpenAI
from app.db.supabase_client import supabase
from app.utils.logger import logger

_ROADMAP_PROMPT = """\
너는 국내 온라인 학습 커리큘럼 설계 전문가야.
사용자의 질문을 분석해서 실제 학습자에게 도움이 되는 구체적인 학습 로드맵을 설계해줘.

## 설계 원칙
1. 사용자의 현재 수준(초급/중급/고급)과 제약(예산, 시간)을 반영해
2. 3~5단계로 구성, 각 단계는 명확한 목표와 예상 기간 포함
3. description은 "왜 이 단계가 필요한지", "무엇을 얻는지" 2~3문장으로 구체적으로
4. search_keywords는 DB에서 강의를 검색할 실제 검색어 (한국어, 짧고 명확하게)
   예: 토익이면 ["토익 LC", "토익 RC", "토익 문법", "TOEIC"] / 일러스트면 ["일러스트", "드로잉", "디지털 드로잉"]
5. bonus_keywords: 유튜브에서 찾을 후기/공부법 검색어 (예: "토익 900점 후기", "토익 공부법")

응답 형식 (JSON만, 마크다운 금지):
{
  "user_level": "초급/중급/고급",
  "goal": "사용자의 최종 목표 구체적으로 한 줄",
  "roadmap": [
    {
      "step": 1,
      "title": "단계 제목",
      "description": "이 단계에서 배워야 할 내용과 이유 2~3문장",
      "duration": "예상 기간 (예: 1~2주)",
      "search_keywords": ["검색어1", "검색어2"],
      "preferred_platforms": ["youtube", "megastudy"],
      "content_types": ["입문강의", "공부법영상"]
    }
  ],
  "bonus_keywords": ["유튜브 후기/공부법 검색어1", "검색어2"],
  "recommended_certs": [
    {
      "name": "자격증/시험 이름 (예: 토익, 정보처리기사, AWS SAA)",
      "why": "이 학습 목표와 연관된 이유 1문장",
      "level": "입문/중급/고급",
      "typical_prep_months": 3
    }
  ]
}
"""

_RERANK_PROMPT = """\
너는 국내 온라인 강의 추천 전문가야.
아래에 학습 로드맵과 각 단계별로 검색된 강의 목록이 주어진다.

## 선별 기준
1. 각 로드맵 단계에서 적합한 강의 2~3개를 골라라 (사용자가 비교해서 선택하게 할 것)
2. 사용자 수준(user_level)에 맞는 강의 우선 — 초급이면 기초/입문, 고급이면 심화
3. "무료" 언급 있으면 is_free=true 강의 반드시 포함
4. 같은 플랫폼 강의 2개 이상 같은 단계에 넣지 말 것
5. 강의가 없는 단계는 건너뛰어도 됨 (억지로 채우지 말 것)
6. 각 강의마다 아래 5가지를 반드시 작성:
   - reason: 왜 이 단계에 적합한지 2~3문장 (학습자 수준과의 매칭, 커리큘럼 특징, 기대 성과)
   - pros: 이 강의의 핵심 장점 3가지를 배열로. 각 항목은 짧고 구체적으로 (예: "실전 문제 위주 구성", "무료 제공", "입문자 눈높이 설명")
   - diff: 같은 단계 다른 후보 강의들 각각과 비교한 차별점. 다른 강의 제목을 언급하며 "A 강의보다 ~한 점이 강점" 형식으로 1~2문장. 경쟁 강의가 없으면 이 강의만의 독보적 특징 1문장
   - fit_score: 이 단계 학습 목표에 얼마나 맞는지 1~10 정수
   - caution: 이 강의를 선택할 때 주의할 점 또는 단점 1문장 (없으면 빈 문자열)

응답 형식 (JSON만, 설명 금지):
{
  "step_groups": [
    {
      "step": 로드맵단계번호,
      "candidates": [
        {
          "id": 강의ID,
          "reason": "이 단계에 적합한 이유 2~3문장",
          "pros": ["장점1", "장점2", "장점3"],
          "diff": "같은 단계 다른 후보들과 비교한 차별점 1~2문장",
          "fit_score": 8,
          "caution": "주의할 점 또는 단점 (없으면 빈 문자열)"
        }
      ]
    }
  ]
}
← 단계 순서대로, 단계당 후보 2~3개
"""


@lru_cache(maxsize=1)
def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _search_lectures_for_step(keywords: list[str], limit: int = 15) -> list[dict]:
    """단계 키워드로 DB에서 관련 강의 검색."""
    if not keywords:
        return []
    try:
        or_filter = ",".join(f"title.ilike.%{kw}%" for kw in keywords[:4])
        rows = (
            supabase.table("lectures")
            .select("id,title,platform,is_free,price,tags,category,rating,student_count,url,thumbnail_url")
            .or_(or_filter)
            .order("student_count", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return rows
    except Exception as e:
        logger.error(f"단계 강의 검색 실패 ({keywords}): {e}")
        return []


def _fetch_youtube_supplements(topic: str, bonus_keywords: list[str]) -> list[dict]:
    """유튜브 후기·공부법 영상 별도 검색."""
    search_terms = bonus_keywords[:3] + [f"{topic} 공부법", f"{topic} 후기"]
    found: list[dict] = []
    seen_ids: set = set()

    for term in search_terms[:4]:
        try:
            rows = (
                supabase.table("lectures")
                .select("id,title,platform,is_free,price,tags,category,rating,student_count,url,thumbnail_url")
                .eq("platform", "youtube")
                .ilike("title", f"%{term}%")
                .order("student_count", desc=True)
                .limit(4)
                .execute()
                .data
            )
            for r in rows:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    r["roadmap_step"] = 0
                    found.append(r)
        except Exception as e:
            logger.error(f"유튜브 보조 검색 실패 ({term}): {e}")

    logger.info(f"유튜브 보조 콘텐츠: {len(found)}건")
    return found[:4]


def _build_catalog(step_candidates: dict[int, list[dict]]) -> str:
    """단계별 강의 목록을 GPT 입력 텍스트로 변환."""
    lines = []
    for step_num, lectures in step_candidates.items():
        lines.append(f"\n[{step_num}단계 후보 강의]")
        for lec in lectures:
            if lec.get("is_free"):
                price = "무료"
            elif lec.get("price", 0) > 0:
                price = f"{lec['price']:,}원"
            else:
                price = "가격미확인"
            raw_tags = lec.get("tags") or []
            desc_tag = next((t[5:] for t in raw_tags if t.startswith("desc:")), None)
            plain_tags = " ".join(t for t in raw_tags if not any(t.startswith(p) for p in ("desc:", "level:", "curriculum:", "keyword:")))[:40]
            student = lec.get("student_count")
            meta = []
            if student:
                meta.append(f"수강생{student:,}명")
            if plain_tags:
                meta.append(f"태그:{plain_tags}")
            if desc_tag:
                meta.append(f"소개:{desc_tag[:80]}")
            meta_str = " | ".join(meta) if meta else ""
            lines.append(f"  [{lec['id']}] {lec['title']} | {lec['platform']} | {price} | {meta_str}")
    return "\n".join(lines)


def _parse_tags(raw_tags: list[str] | None) -> dict:
    """tags 배열에서 level/desc/curriculum/keyword 파싱."""
    result = {"level": None, "description": None, "curriculum": None, "keywords": []}
    if not raw_tags:
        return result
    for tag in raw_tags:
        if tag.startswith("level:"):
            result["level"] = tag[6:]
        elif tag.startswith("desc:"):
            result["description"] = tag[5:]
        elif tag.startswith("curriculum:"):
            result["curriculum"] = tag[11:]
        elif tag.startswith("keyword:"):
            result["keywords"].append(tag[8:])
    return result


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "").strip()
    return json.loads(raw)


async def _build_roadmap(question: str, client: AsyncOpenAI) -> dict:
    resp = await client.chat.completions.create(
        model="gpt-5.5",
        messages=[
            {"role": "system", "content": _ROADMAP_PROMPT},
            {"role": "user", "content": f"사용자 질문: \"{question}\""},
        ],
        max_completion_tokens=2000,
        timeout=60,
    )
    raw = resp.choices[0].message.content.strip()
    roadmap = _parse_json(raw)
    logger.info(f"로드맵 설계 완료: {len(roadmap.get('roadmap', []))}단계 — {roadmap.get('goal', '')}")
    return roadmap


async def select_lectures_by_ai(question: str) -> tuple[dict, list[dict], list[dict]]:
    """로드맵 설계 → 단계별 DB 검색 → GPT 선별.

    반환: (roadmap, yt_supplements, step_groups)
    step_groups: [{"step": int, "candidates": [Lecture + reason + diff]}]
    """
    client = _get_client()

    try:
        roadmap = await _build_roadmap(question, client)
    except Exception as e:
        logger.error(f"로드맵 설계 실패: {e}")
        roadmap = {"user_level": "초급", "goal": question, "roadmap": [], "bonus_keywords": []}

    steps = roadmap.get("roadmap", [])
    bonus_keywords = roadmap.get("bonus_keywords", [])
    goal = roadmap.get("goal", question)

    # 핵심 주제어 추출
    topic_match = re.search(r'[가-힣A-Za-z]+', question)
    topic = topic_match.group(0) if topic_match else question[:4]

    # 2단계: 각 로드맵 단계별로 DB에서 관련 강의 검색
    step_candidates: dict[int, list[dict]] = {}
    all_lec_ids: set = set()

    for step in steps:
        step_num = step["step"]
        keywords = step.get("search_keywords") or step.get("keywords") or []
        lectures = _search_lectures_for_step(keywords, limit=15)

        # 중복 제거
        unique = []
        for lec in lectures:
            if lec["id"] not in all_lec_ids:
                all_lec_ids.add(lec["id"])
                unique.append(lec)

        step_candidates[step_num] = unique
        logger.info(f"  [{step_num}단계] '{', '.join(keywords[:2])}' → {len(unique)}건")

    total_candidates = sum(len(v) for v in step_candidates.values())
    logger.info(f"단계별 후보 합산: {total_candidates}건")

    # 유튜브 보조 콘텐츠
    yt_supplements = _fetch_youtube_supplements(topic, bonus_keywords)
    yt_supp_ids = {r["id"] for r in yt_supplements}

    # 3단계: GPT가 단계별 강의 목록 보고 최적 선별
    catalog = _build_catalog(step_candidates)
    roadmap_text = json.dumps(
        {"user_level": roadmap.get("user_level"), "goal": goal, "roadmap": steps},
        ensure_ascii=False, indent=2
    )
    prompt = (
        f"사용자 질문: \"{question}\"\n"
        f"사용자 수준: {roadmap.get('user_level', '초급')}\n\n"
        f"## 학습 로드맵\n{roadmap_text}\n\n"
        f"## 단계별 검색된 강의 목록\n{catalog}"
    )

    all_lecs = {lec["id"]: lec for step_lecs in step_candidates.values() for lec in step_lecs}

    try:
        resp = await client.chat.completions.create(
            model="gpt-5.5",
            messages=[
                {"role": "system", "content": _RERANK_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=4000,
            timeout=90,
        )
        raw = resp.choices[0].message.content
        finish_reason = resp.choices[0].finish_reason
        logger.info(f"GPT rerank 응답: finish_reason={finish_reason}, len={len(raw or '')}, preview={repr((raw or '')[:200])}")
        raw = (raw or "").strip()
        if not raw:
            raise ValueError(f"빈 응답 (finish_reason={finish_reason})")
        result = _parse_json(raw)

        step_groups: list[dict] = []
        flat_lectures: list[dict] = []

        for group in result.get("step_groups") or []:
            step_num = group.get("step")
            # 이 단계에서 선별된 강의 ID 목록 (diff 주입용)
            valid_items = [
                item for item in (group.get("candidates") or [])
                if item.get("id") in all_lecs and item.get("id") not in yt_supp_ids
            ]
            selected_titles = {item["id"]: all_lecs[item["id"]]["title"] for item in valid_items}

            candidates_out = []
            for item in valid_items:
                lec_id = item.get("id")
                lec = dict(all_lecs[lec_id])
                parsed = _parse_tags(lec.get("tags"))
                lec["level"] = parsed["level"]
                lec["description"] = parsed["description"]
                lec["curriculum"] = parsed["curriculum"]
                lec["keywords"] = parsed["keywords"]
                lec["tags"] = [t for t in (lec.get("tags") or [])
                               if not any(t.startswith(p) for p in ("level:", "desc:", "curriculum:", "keyword:"))]
                lec["roadmap_step"] = step_num
                lec["reason"] = item.get("reason", "")
                lec["pros"] = item.get("pros", [])
                lec["fit_score"] = item.get("fit_score")
                lec["caution"] = item.get("caution", "")

                # diff: GPT 응답이 있으면 사용, 없으면 같은 단계 경쟁 강의 제목 기반으로 생성
                ai_diff = item.get("diff", "")
                if ai_diff:
                    lec["diff"] = ai_diff
                else:
                    rivals = [t for lid, t in selected_titles.items() if lid != lec_id]
                    if rivals:
                        lec["diff"] = f"이 단계의 다른 후보 강의({', '.join(rivals)})와 함께 비교해보세요."
                    else:
                        lec["diff"] = ""

                candidates_out.append(lec)
                flat_lectures.append(lec)
            if candidates_out:
                step_groups.append({"step": step_num, "candidates": candidates_out})

        logger.info(f"AI 선별 완료: {total_candidates}건 → 보조:{len(yt_supplements)} + {len(step_groups)}단계 / {len(flat_lectures)}강의")
        return roadmap, yt_supplements, step_groups

    except Exception as e:
        logger.error(f"AI 선별 실패: {e}")
        def _enrich(lec: dict, sn: int) -> dict:
            lec = dict(lec)
            parsed = _parse_tags(lec.get("tags"))
            lec["level"] = parsed["level"]
            lec["description"] = parsed["description"]
            lec["curriculum"] = parsed["curriculum"]
            lec["keywords"] = parsed["keywords"]
            lec["tags"] = [t for t in (lec.get("tags") or [])
                           if not any(t.startswith(p) for p in ("level:", "desc:", "curriculum:", "keyword:"))]
            lec["roadmap_step"] = sn
            lec["reason"] = ""
            lec["pros"] = []
            lec["diff"] = ""
            lec["fit_score"] = None
            lec["caution"] = ""
            return lec

        fallback_groups = [
            {"step": sn, "candidates": [_enrich(lec, sn) for lec in lecs[:3]]}
            for sn, lecs in step_candidates.items() if lecs
        ]
        fallback_flat = [lec for lecs in step_candidates.values() for lec in lecs[:3]]
        return roadmap, yt_supplements, fallback_groups
