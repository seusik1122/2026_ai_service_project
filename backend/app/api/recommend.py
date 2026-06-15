"""POST /api/recommend — GPT 로드맵 설계 → 강의 선별."""
import os
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.ai.recommend import select_lectures_by_ai
from app.db.queries import get_exams
from app.utils.logger import logger

router = APIRouter()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "kkhlhj485@gmail.com")


class RecommendRequest(BaseModel):
    question: str
    limit: int = 10


class RecommendEmailRequest(BaseModel):
    question: str
    email: str
    roadmap: dict
    lectures: list[dict]  # 사용자가 선택한 강의만
    certs: Optional[list[dict]] = None  # recommended_certs from roadmap


def _build_email_html(question: str, roadmap: dict, lectures: list[dict], certs: list[dict] | None = None) -> str:
    goal = roadmap.get("goal", question)
    level = roadmap.get("user_level", "초급")
    steps = roadmap.get("roadmap", [])
    yt_lectures = [l for l in lectures if l.get("roadmap_step") == 0]
    main_lectures = [l for l in lectures if l.get("roadmap_step") != 0]
    recommended_certs = certs or roadmap.get("recommended_certs") or []

    level_color = {"초급": "#22c55e", "중급": "#f59e0b", "고급": "#ef4444"}.get(level, "#6366f1")

    # 로드맵 단계 HTML
    steps_html = ""
    for i, step in enumerate(steps):
        duration = step.get("duration", "")
        connector = '<div style="width:2px;height:20px;background:#ddd6fe;margin:4px auto;"></div>' if i < len(steps) - 1 else ""
        steps_html += f"""
        <div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:4px;">
          <div style="flex-shrink:0;width:32px;height:32px;border-radius:50%;background:#6366f1;color:#fff;
                      font-weight:700;font-size:14px;line-height:32px;text-align:center;">{step['step']}</div>
          <div style="flex:1;background:#f8f7ff;border-radius:10px;padding:12px 14px;border-left:3px solid #6366f1;">
            <div style="font-weight:700;color:#1e1b4b;font-size:14px;">{step['title']}{"&nbsp;&nbsp;<span style='font-size:11px;color:#6366f1;'>⏱ " + duration + "</span>" if duration else ""}</div>
            <div style="font-size:12px;color:#6b7280;margin-top:4px;line-height:1.6;">{step.get('description', '')}</div>
          </div>
        </div>
        {connector}"""

    # 가격 배지
    def price_badge(lec: dict) -> str:
        if lec.get("is_free"):
            return '<span style="background:#dcfce7;color:#16a34a;font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600;">무료</span>'
        p = lec.get("price", 0)
        return (f'<span style="background:#fff7ed;color:#ea580c;font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600;">{p:,}원</span>'
                if p else '<span style="background:#f3f4f6;color:#6b7280;font-size:11px;padding:2px 8px;border-radius:20px;">가격 미확인</span>')

    # fit_score 바
    def fit_bar(score: int | None) -> str:
        if not score:
            return ""
        pct = int(score * 10)
        color = "#22c55e" if score >= 8 else "#f59e0b" if score >= 6 else "#ef4444"
        return f"""<div style="margin-top:8px;">
          <div style="font-size:11px;color:#6b7280;margin-bottom:3px;">적합도 <b style="color:{color};">{score}/10</b></div>
          <div style="background:#f3f4f6;border-radius:99px;height:6px;overflow:hidden;">
            <div style="width:{pct}%;background:{color};height:6px;border-radius:99px;"></div>
          </div>
        </div>"""

    # 선택 강의 HTML
    lectures_html = ""
    for lec in main_lectures:
        step_num = lec.get("roadmap_step")
        url = lec.get("url", "")
        rating = lec.get("rating")
        student = lec.get("student_count")
        keywords = lec.get("keywords") or []
        pros = lec.get("pros") or []
        description = lec.get("description", "")
        curriculum = lec.get("curriculum", "")

        step_badge = f'<span style="background:#e0e7ff;color:#4338ca;font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600;margin-right:4px;">{step_num}단계</span>' if step_num else ""
        platform_badge = f'<span style="background:#f3f4f6;color:#374151;font-size:11px;padding:2px 8px;border-radius:20px;margin-right:4px;">{lec["platform"]}</span>'

        meta_parts = []
        if rating is not None:
            meta_parts.append(f'⭐ {rating:.1f}')
        if student:
            meta_parts.append(f'👥 {student:,}명')
        meta_str = "&nbsp;&nbsp;".join(meta_parts)

        reason_html = (f'<div style="margin-top:10px;padding:10px 12px;background:#eff6ff;border-radius:8px;'
                       f'font-size:12px;color:#1d4ed8;line-height:1.7;border-left:3px solid #3b82f6;">'
                       f'<b>📋 추천 이유</b><br>{lec["reason"]}</div>') if lec.get("reason") else ""

        pros_items = "".join(f'<li style="margin-bottom:3px;">{p}</li>' for p in pros)
        pros_html = (f'<div style="margin-top:8px;padding:10px 12px;background:#f0fdf4;border-radius:8px;'
                     f'font-size:12px;color:#15803d;border-left:3px solid #22c55e;">'
                     f'<b>✅ 핵심 장점</b>'
                     f'<ul style="margin:6px 0 0 0;padding-left:18px;line-height:1.7;">{pros_items}</ul></div>') if pros else ""

        diff_html = (f'<div style="margin-top:8px;padding:10px 12px;background:#eef2ff;border-radius:8px;'
                     f'font-size:12px;color:#4338ca;line-height:1.7;border-left:3px solid #6366f1;">'
                     f'<b>⚡ 차별점</b><br>{lec["diff"]}</div>') if lec.get("diff") else ""

        desc_html = (f'<div style="margin-top:8px;font-size:12px;color:#4b5563;line-height:1.7;">{description}</div>') if description else ""

        curr_html = (f'<div style="margin-top:8px;padding:8px 10px;background:#faf5ff;border-radius:8px;'
                     f'font-size:12px;color:#7e22ce;line-height:1.7;border-left:3px solid #a855f7;">'
                     f'<b>📖 커리큘럼</b><br>{curriculum}</div>') if curriculum else ""

        caution_html = (f'<div style="margin-top:8px;padding:8px 10px;background:#fffbeb;border-radius:8px;'
                        f'font-size:12px;color:#92400e;line-height:1.7;border-left:3px solid #f59e0b;">'
                        f'⚠️ {lec["caution"]}</div>') if lec.get("caution") else ""

        kw_tags = "".join(f'<span style="display:inline-block;background:#dbeafe;color:#1d4ed8;font-size:11px;'
                          f'padding:2px 8px;border-radius:20px;margin:2px 2px 0 0;">{kw}</span>' for kw in keywords[:6])
        kw_html = f'<div style="margin-top:8px;">{kw_tags}</div>' if kw_tags else ""

        link_btn = (f'<a href="{url}" style="display:inline-block;margin-top:12px;padding:8px 18px;'
                    f'background:#6366f1;color:#fff;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;">'
                    f'강의 바로가기 →</a>') if url else ""

        lectures_html += f"""
        <div style="border:1px solid #e5e7eb;border-radius:14px;padding:18px;margin-bottom:14px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
          <div style="margin-bottom:8px;">{step_badge}{platform_badge}{price_badge(lec)}</div>
          <div style="font-weight:700;color:#111827;font-size:16px;line-height:1.4;">{lec['title']}</div>
          {"<div style='font-size:12px;color:#9ca3af;margin-top:3px;'>강사: " + lec['instructor_name'] + "</div>" if lec.get('instructor_name') else ""}
          {"<div style='font-size:12px;color:#6b7280;margin-top:3px;'>" + meta_str + "</div>" if meta_str else ""}
          {fit_bar(lec.get("fit_score"))}
          {desc_html}
          {reason_html}
          {pros_html}
          {diff_html}
          {curr_html}
          {caution_html}
          {kw_html}
          {link_btn}
        </div>"""

    # 유튜브 보조 HTML
    yt_html = ""
    if yt_lectures:
        yt_items = ""
        for lec in yt_lectures:
            url = lec.get("url", "")
            yt_items += (f'<a href="{url}" style="display:block;padding:10px 14px;background:#fff;'
                         f'border:1px solid #fee2e2;border-radius:10px;text-decoration:none;margin-bottom:8px;">'
                         f'<span style="font-size:13px;color:#dc2626;font-weight:600;">▶ </span>'
                         f'<span style="font-size:13px;color:#374151;">{lec["title"]}</span></a>')
        yt_html = f"""
        <div style="margin-top:32px;">
          <h2 style="font-size:15px;font-weight:700;color:#111827;margin:0 0 12px;">🎬 유튜브 추천 영상</h2>
          {yt_items}
        </div>"""

    # 자격증 섹션 HTML
    certs_html = ""
    if recommended_certs:
        cert_cards = ""
        for cert in recommended_certs:
            cert_name = cert.get("name", "")
            cert_why = cert.get("why", "")
            cert_level = cert.get("level", "")
            prep_months = cert.get("typical_prep_months")

            # DB에서 시험 일정 조회
            exam_rows = []
            try:
                exam_rows = get_exams(keyword=cert_name, d_day_within=365)
            except Exception:
                pass

            level_badge_color = {"입문": "#22c55e", "중급": "#f59e0b", "고급": "#ef4444"}.get(cert_level, "#6366f1")
            level_badge = f'<span style="background:{level_badge_color};color:#fff;font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600;margin-right:6px;">{cert_level}</span>' if cert_level else ""
            prep_str = f'<span style="background:#f3f4f6;color:#6b7280;font-size:11px;padding:2px 8px;border-radius:20px;">준비기간 약 {prep_months}개월</span>' if prep_months else ""

            # 시험 일정 행
            schedule_rows = ""
            for exam in exam_rows[:3]:
                d_day = exam.get("d_day")
                exam_date = exam.get("exam_date", "")
                app_start = exam.get("application_start", "")
                app_end = exam.get("application_end", "")
                result_date = exam.get("result_date", "")
                exam_type = exam.get("exam_type", "")

                if d_day is not None:
                    if d_day == 0:
                        dday_str = "D-Day"
                        dday_color = "#ef4444"
                    elif d_day > 0:
                        dday_str = f"D-{d_day}"
                        dday_color = "#ef4444" if d_day <= 30 else "#f59e0b" if d_day <= 90 else "#6366f1"
                    else:
                        dday_str = f"D+{abs(d_day)} (종료)"
                        dday_color = "#9ca3af"
                else:
                    dday_str = "일정 미정"
                    dday_color = "#9ca3af"

                type_label = f"[{exam_type}] " if exam_type else ""
                date_detail = ""
                if app_start and app_end:
                    date_detail += f"접수: {app_start} ~ {app_end}"
                if exam_date:
                    date_detail += f" &nbsp;|&nbsp; 시험: {exam_date}"
                if result_date:
                    date_detail += f" &nbsp;|&nbsp; 발표: {result_date}"

                schedule_rows += f"""
                <div style="padding:8px 0;border-bottom:1px solid #f3f4f6;">
                  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:4px;">
                    <span style="font-size:12px;font-weight:600;color:#1e1b4b;">{type_label}{exam.get('exam_name', cert_name)}</span>
                    <span style="font-size:12px;font-weight:700;color:{dday_color};">{dday_str}</span>
                  </div>
                  {"<div style='font-size:11px;color:#6b7280;margin-top:3px;'>" + date_detail + "</div>" if date_detail else ""}
                </div>"""

            schedule_section = (
                f'<div style="margin-top:10px;border-top:1px solid #e5e7eb;padding-top:8px;">'
                f'<div style="font-size:11px;font-weight:600;color:#6b7280;margin-bottom:4px;">📅 시험 일정</div>'
                f'{schedule_rows}'
                f'</div>'
            ) if schedule_rows else (
                '<div style="margin-top:8px;font-size:11px;color:#9ca3af;">등록된 시험 일정이 없습니다.</div>'
            )

            cert_cards += f"""
            <div style="border:1px solid #e0e7ff;border-radius:12px;padding:14px 16px;margin-bottom:10px;background:#fafafa;">
              <div style="margin-bottom:6px;">{level_badge}{prep_str}</div>
              <div style="font-weight:700;color:#1e1b4b;font-size:14px;">🏆 {cert_name}</div>
              {"<div style='font-size:12px;color:#4b5563;margin-top:4px;line-height:1.6;'>" + cert_why + "</div>" if cert_why else ""}
              {schedule_section}
            </div>"""

        certs_html = f"""
        <div style="margin-top:32px;">
          <h2 style="font-size:15px;font-weight:700;color:#111827;margin:0 0 4px;">🏆 관련 자격증 & 시험 일정</h2>
          <p style="font-size:12px;color:#9ca3af;margin:0 0 14px;">학습 목표와 연관된 자격증 및 최신 일정입니다.</p>
          {cert_cards}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f5f3ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:600px;margin:32px auto;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(99,102,241,0.10);">

    <!-- 헤더 -->
    <div style="background:linear-gradient(135deg,#4f46e5,#818cf8);padding:32px 32px 28px;">
      <div style="font-size:11px;color:#c7d2fe;font-weight:700;letter-spacing:1.5px;margin-bottom:10px;">AI 강의 추천 시스템</div>
      <h1 style="margin:0;font-size:22px;font-weight:800;color:#fff;line-height:1.3;">📚 맞춤 학습 로드맵</h1>
      <div style="margin-top:10px;font-size:14px;color:#e0e7ff;line-height:1.5;">"{question}"</div>
    </div>

    <!-- 목표 요약 -->
    <div style="padding:18px 32px;background:#f8f7ff;border-bottom:1px solid #e5e7eb;">
      <table style="border-collapse:collapse;width:100%;"><tr>
        <td style="vertical-align:middle;padding-right:10px;">
          <span style="background:{level_color};color:#fff;font-size:12px;font-weight:700;padding:4px 14px;border-radius:20px;">{level}</span>
        </td>
        <td style="vertical-align:middle;font-size:13px;color:#374151;line-height:1.5;">🎯 {goal}</td>
      </tr></table>
    </div>

    <div style="padding:28px 32px;">

      <!-- 로드맵 -->
      <h2 style="font-size:15px;font-weight:700;color:#111827;margin:0 0 16px;">📍 학습 로드맵</h2>
      {steps_html}

      <!-- 선택 강의 -->
      <h2 style="font-size:15px;font-weight:700;color:#111827;margin:32px 0 12px;">🎓 내가 선택한 강의</h2>
      {lectures_html if lectures_html else '<p style="color:#9ca3af;font-size:13px;">선택된 강의가 없습니다.</p>'}

      {yt_html}

      {certs_html}

    </div>

    <!-- 푸터 -->
    <div style="padding:20px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;text-align:center;">
      <p style="margin:0;font-size:12px;color:#9ca3af;">AI 강의 추천 시스템이 자동으로 생성한 결과입니다.</p>
    </div>

  </div>
</body>
</html>"""
    return html


async def _send_via_zapier(to: str, subject: str, body: str) -> bool:
    url = os.getenv("ZAPIER_DDAY_WEBHOOK_URL")
    if not url:
        logger.warning("ZAPIER_DDAY_WEBHOOK_URL 미설정 — 이메일 전송 불가")
        return False
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"to": to, "subject": subject, "body": body, "html_body": body}, timeout=10)
        logger.info(f"추천 이메일 전송 완료: {to}")
        return True
    except Exception as e:
        logger.error(f"추천 이메일 전송 실패: {e}")
        return False


@router.post("/recommend")
async def recommend_lectures(body: RecommendRequest):
    roadmap, yt_supplements, step_groups = await select_lectures_by_ai(body.question)
    flat = [lec for g in step_groups for lec in g["candidates"]]
    return {
        "question": body.question,
        "roadmap": roadmap,
        "yt_supplements": yt_supplements,
        "step_groups": step_groups,
        "total": len(flat),
        "lectures": flat,
    }


@router.post("/recommend/email")
async def recommend_email(body: RecommendEmailRequest):
    """추천 결과(로드맵 + 강의 링크)를 이메일로 전송."""
    subject = f"[AI 추천] {body.question} — 학습 로드맵 & 강의 링크"
    email_body = _build_email_html(body.question, body.roadmap, body.lectures, body.certs)
    ok = await _send_via_zapier(body.email, subject, email_body)
    if ok:
        return {"status": "ok", "message": f"{body.email}로 전송했습니다."}
    return {"status": "error", "message": "이메일 전송에 실패했습니다. 잠시 후 다시 시도해주세요."}
