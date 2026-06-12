# 큐넷 국가자격시험 일정 수집기 (공공데이터포털, XML 응답)
# 명세서 섹션 5:
#   엔드포인트: .../InquiryQualExamSchdulInfo/getList
#   파라미터: ServiceKey, implYy(연도)
#   저장: upsert_exam() 호출
#   D-day 계산: update_exam_dday() 가 매일 자동 실행 (여기선 d_day=None 으로 저장)
#
# 큐넷 API는 한 종목 레코드에 필기(doc*)·실기(prac*) 일정이 함께 담겨 오므로
# exam_type='필기' / '실기' 두 행으로 분리해 저장한다(on_conflict=exam_name,exam_type).
import os
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional

import requests

from app.db.queries import upsert_exam, update_exam_dday
from app.db.models import ExamCreate
from app.utils.logger import logger

QNET_API_URL = "https://openapi.q-net.or.kr/api/service/rest/InquiryQualExamSchdulInfo/getList"


def collect_qnet_exams(year: Optional[int] = None) -> int:
    """큐넷 자격증 시험 일정을 수집해 upsert_exam()으로 저장. 저장 건수 반환."""
    impl_yy = year or date.today().year
    params = {"ServiceKey": os.getenv("QNET_API_KEY"), "implYy": str(impl_yy)}

    try:
        resp = requests.get(QNET_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        items = _parse_items(resp.text)
    except Exception as e:
        logger.error(f"큐넷 API 실패: {e}")
        return 0

    saved = 0
    for item in items:
        for exam in _to_exams(item):
            try:
                upsert_exam(exam)
                saved += 1
            except Exception as e:
                logger.error(f"큐넷 저장 실패: {exam.exam_name}/{exam.exam_type} — {e}")

    logger.info(f"큐넷 수집 완료: {saved}건")
    # 수집 직후 전체 d_day 초기 계산 (이후 매일 스케줄러가 갱신)
    try:
        update_exam_dday()
    except Exception as e:
        logger.error(f"d_day 계산 실패 — {e}")
    return saved


def _parse_items(xml_text: str) -> list[dict]:
    """XML 응답을 파싱해 <item> 요소들을 dict 리스트로 반환."""
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for item_el in root.findall(".//item"):
        items.append({child.tag: (child.text or "").strip() for child in item_el})
    return items


def _to_exams(item: dict) -> list[ExamCreate]:
    """한 종목 레코드를 필기/실기 ExamCreate 행으로 분리."""
    # 종목명 필드는 데이터셋에 따라 다를 수 있어 후보를 순차 탐색
    exam_name = (
        item.get("jmfldnm")
        or item.get("jmNm")
        or item.get("description")
        or item.get("qualgbNm")
        or ""
    ).strip()
    if not exam_name:
        return []

    exams: list[ExamCreate] = []
    # 필기 (doc*)
    written = _build(exam_name, "필기",
                     item.get("docRegStartDt"), item.get("docRegEndDt"),
                     item.get("docExamStartDt"), item.get("docPassDt"))
    if written:
        exams.append(written)
    # 실기 (prac*)
    practical = _build(exam_name, "실기",
                       item.get("pracRegStartDt"), item.get("pracRegEndDt"),
                       item.get("pracExamStartDt"), item.get("pracPassDt"))
    if practical:
        exams.append(practical)
    return exams


def _build(name: str, exam_type: str, reg_start, reg_end, exam_start, pass_date) -> Optional[ExamCreate]:
    reg_s, reg_e = _iso(reg_start), _iso(reg_end)
    exam_d, result_d = _iso(exam_start), _iso(pass_date)
    if not any([reg_s, reg_e, exam_d, result_d]):
        return None  # 해당 유형(필기/실기) 일정이 없으면 행 생성 안 함
    return ExamCreate(
        exam_name=name,
        exam_type=exam_type,
        application_start=reg_s,
        application_end=reg_e,
        exam_date=exam_d,
        result_date=result_d,
        d_day=None,  # update_exam_dday()가 계산
        related_keywords=[name],
    )


def _iso(yyyymmdd: Optional[str]) -> Optional[str]:
    """'20240301' → '2024-03-01'. 형식이 맞지 않으면 None."""
    if not yyyymmdd:
        return None
    s = yyyymmdd.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return None
