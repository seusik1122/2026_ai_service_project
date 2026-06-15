import asyncio
import re
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.db.models import ExamCreate
from app.db.queries import upsert_exam, update_exam_dday
from app.utils.logger import logger

CATEGORY_EXAM_MAP: dict[str, list[str]] = {
    "IT/개발":          ["정보처리기사", "정보처리산업기사", "컴퓨터활용능력 1급", "컴퓨터활용능력 2급", "정보보안기사", "리눅스마스터 1급", "네트워크관리사 2급"],
    "AI/머신러닝":       ["정보처리기사", "SQLD", "SQLP", "빅데이터분석기사", "ADsP", "ADP"],
    "데이터사이언스":     ["정보처리기사", "SQLD", "SQLP", "빅데이터분석기사", "ADsP", "ADP"],
    "어학":             ["TOEIC", "TEPS", "OPIc", "IELTS", "TOEFL", "TOEIC Speaking"],
    "토익":             ["TOEIC", "TOEIC Speaking"],
    "텝스":             ["TEPS"],
    "전기/안전":         ["전기기사", "전기산업기사", "전기공사기사", "전기기능사", "전기공사산업기사"],
    "세무/회계":         ["세무사", "전산세무 1급", "전산회계운용사 1급", "전산세무 2급", "전산회계 1급"],
    "디자인":           ["컬러리스트기사", "GTQ(포토샵)", "GTQ(일러스트)", "시각디자인기사", "게임그래픽전문가"],
    "캐릭터":           ["컬러리스트기사", "GTQ(포토샵)", "GTQ(일러스트)", "게임그래픽전문가"],
    "3D":              ["컬러리스트기사", "게임그래픽전문가"],
    "건축":             ["건축기사", "건축산업기사"],
    "소방":             ["소방설비기사(기계분야)", "소방설비기사(전기분야)", "소방설비산업기사(기계분야)", "소방설비산업기사(전기분야)"],
    "공무원":           ["한국사능력검정시험"],
    "재테크":           ["공인중개사", "펀드투자권유자문인력", "증권투자권유자문인력", "투자자산운용사"],
    "창업":             ["공인중개사"],
    "요리/카페":         ["한식조리기능사", "양식조리기능사", "제과기능사", "제빵기능사", "바리스타"],
    "제빵":             ["제과기능사", "제빵기능사"],
    "헤어":             ["미용사(일반)", "미용사(피부)", "미용사(네일)"],
    "피트니스":         ["생활스포츠지도사 2급", "건강운동관리사"],
    "영상제작":         ["영상편집기사"],
    "IT자격증":         ["컴퓨터활용능력 1급", "컴퓨터활용능력 2급", "ITQ", "MOS", "워드프로세서"],
    "게임프로그래밍":    ["정보처리기사", "게임그래픽전문가"],
    "비즈니스/IT":      ["컴퓨터활용능력 1급", "워드프로세서", "정보처리기사"],
}

# 큐넷 종목코드 → (exam_name, related_keywords)
QNET_EXAMS: list[tuple[str, str, list[str]]] = [
    # 전기
    ("1150", "전기기사",           ["전기기사", "전기", "전기공사", "전기기술"]),
    ("2140", "전기산업기사",        ["전기산업기사", "전기"]),
    ("1160", "전기공사기사",        ["전기공사기사", "전기공사", "전기"]),
    ("2150", "전기공사산업기사",     ["전기공사산업기사", "전기공사"]),
    ("7120", "전기기능사",          ["전기기능사", "전기"]),
    # IT/정보
    ("1320", "정보처리기사",        ["정보처리기사", "정보처리", "IT", "개발"]),
    ("2290", "정보처리산업기사",     ["정보처리산업기사", "정보처리"]),
    ("1325", "정보보안기사",        ["정보보안기사", "정보보안", "보안", "해킹"]),
    # 컬러/디자인
    ("1982", "컬러리스트기사",       ["컬러리스트", "색채", "디자인"]),
    ("2982", "컬러리스트산업기사",   ["컬러리스트", "색채"]),
    # 건축
    ("1630", "건축기사",            ["건축기사", "건축"]),
    ("2630", "건축산업기사",         ["건축산업기사", "건축"]),
    # 소방
    ("1900", "소방설비기사(기계분야)", ["소방설비기사", "소방기계"]),
    ("1910", "소방설비기사(전기분야)", ["소방설비기사", "소방전기"]),
    ("2900", "소방설비산업기사(기계분야)", ["소방설비산업기사", "소방기계"]),
    ("2910", "소방설비산업기사(전기분야)", ["소방설비산업기사", "소방전기"]),
    # 부동산/금융
    ("9630", "공인중개사",          ["공인중개사", "부동산", "재테크"]),
    ("9641", "세무사",              ["세무사", "세무", "회계"]),
    # 조리
    ("7760", "한식조리기능사",       ["한식조리기능사", "조리", "요리", "한식", "한식조리"]),
    ("7770", "양식조리기능사",       ["양식조리기능사", "조리", "요리", "양식"]),
    ("7900", "제과기능사",           ["제과기능사", "제과", "제빵", "베이킹"]),
    ("7910", "제빵기능사",           ["제빵기능사", "제빵", "베이킹", "빵"]),
    # 미용
    ("7640", "미용사(일반)",         ["미용사", "헤어", "헤어디자이너"]),
    ("7641", "미용사(피부)",         ["미용사", "피부", "피부관리"]),
    ("7643", "미용사(네일)",         ["미용사", "네일"]),
    # 시각/영상
    ("1971", "시각디자인기사",       ["시각디자인", "디자인", "그래픽"]),
    # 빅데이터
    ("1492", "빅데이터분석기사",     ["빅데이터", "데이터분석", "데이터사이언스", "AI", "머신러닝", "파이썬", "python"]),
    # 산업안전
    ("1120", "산업안전기사",         ["산업안전", "안전관리", "안전"]),
    ("2120", "산업안전산업기사",      ["산업안전산업기사", "안전관리"]),
    # 건설안전
    ("1131", "건설안전기사",         ["건설안전", "안전", "건설"]),
    # 기계
    ("1660", "일반기계기사",         ["일반기계", "기계", "기계설계"]),
    ("1662", "기계설계기사",         ["기계설계", "기계", "설계"]),
    # 화학
    ("1820", "화학분석기능사",       ["화학분석", "화학", "분석화학"]),
    # 환경
    ("1780", "대기환경기사",         ["대기환경", "환경", "환경기사"]),
    ("1790", "수질환경기사",         ["수질환경", "환경", "수질"]),
    ("1800", "환경기능사",           ["환경기능사", "환경"]),
    # 스포츠
    ("4180", "생활스포츠지도사 2급", ["생활스포츠지도사", "스포츠", "피트니스", "운동"]),
    ("4181", "건강운동관리사",       ["건강운동관리사", "운동", "헬스", "피트니스"]),
    # 정보통신
    ("1330", "정보통신기사",         ["정보통신", "통신", "네트워크"]),
    # 품질
    ("1440", "품질경영기사",         ["품질경영", "품질", "QM"]),
    # 용접
    ("7730", "용접기능사",           ["용접기능사", "용접"]),
    # 냉동공조
    ("7050", "냉동공조기능사",       ["냉동공조", "에어컨", "냉동"]),
]

# requests 기반 크롤러 대상 (비큐넷)
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}


def _first_date(text: str) -> Optional[str]:
    text = re.sub(r'\[.*?\]', '', text)
    m = re.search(r'(\d{4}\.\d{2}\.\d{2})', text)
    if m:
        return m.group(1).replace('.', '-')
    m2 = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    return m2.group(1) if m2 else None


def _last_date(text: str) -> Optional[str]:
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'빈자리.*', '', text, flags=re.DOTALL)
    dates = re.findall(r'\d{4}\.\d{2}\.\d{2}', text)
    return dates[-1].replace('.', '-') if dates else None


def _parse_qnet_table(html: str, exam_name: str, keywords: list[str]) -> list[ExamCreate]:
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    if not tables:
        return []

    results: list[ExamCreate] = []
    rows = tables[0].find_all('tr')

    for row in rows[1:]:
        cells = row.find_all('td')
        if len(cells) < 7:
            continue
        raw = [' '.join(c.stripped_strings) for c in cells]

        round_label = raw[0].strip()

        written = ExamCreate(
            exam_name=exam_name,
            exam_type="필기",
            application_start=_first_date(raw[1]),
            application_end=_last_date(raw[1]),
            exam_date=_first_date(raw[2]),
            result_date=_first_date(raw[3]),
            d_day=None,
            related_keywords=keywords + ([round_label] if round_label else []),
        )
        if written.application_start or written.exam_date:
            results.append(written)

        practical = ExamCreate(
            exam_name=exam_name,
            exam_type="실기",
            application_start=_first_date(raw[4]),
            application_end=_last_date(raw[4]),
            exam_date=_first_date(raw[5]),
            result_date=_first_date(raw[6]),
            d_day=None,
            related_keywords=keywords + ([round_label] if round_label else []),
        )
        if practical.application_start or practical.exam_date:
            results.append(practical)

    return results


async def _crawl_qnet_exam(
    jm_cd: str,
    exam_name: str,
    keywords: list[str],
    page,
) -> list[ExamCreate]:
    try:
        url = f'https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd={jm_cd}'
        await page.goto(url, wait_until='domcontentloaded', timeout=25000)
        await page.wait_for_timeout(1500)
        html = await page.content()

        if not BeautifulSoup(html, 'html.parser').find_all('table'):
            await page.goto('https://www.q-net.or.kr/crf005.do?id=crf00503',
                            wait_until='networkidle', timeout=25000)
            await page.wait_for_timeout(1000)
            await page.evaluate(f'''() => {{
                var f = document.forms[0];
                f.jmCd.value = "{jm_cd}";
                f.method = "post";
                f.submit();
            }}''')
            await page.wait_for_load_state('domcontentloaded')
            await page.wait_for_timeout(2000)
            html = await page.content()

        exams = _parse_qnet_table(html, exam_name, keywords)

        today = date.today()
        compressed: dict[str, ExamCreate] = {}
        for e in exams:
            if e.exam_date:
                try:
                    d = date.fromisoformat(e.exam_date)
                except ValueError:
                    continue
                key = e.exam_type
                existing = compressed.get(key)
                if existing is None:
                    compressed[key] = e
                else:
                    existing_d = date.fromisoformat(existing.exam_date) if existing.exam_date else date.min
                    if d >= today and (existing_d < today or d < existing_d):
                        compressed[key] = e

        final = list(compressed.values()) if compressed else exams[:2]
        logger.info(f'큐넷 [{exam_name}] {len(final)}건')
        return final

    except Exception as e:
        logger.error(f'큐넷 [{exam_name}] 실패: {e}')
        return []


async def _crawl_toeic(page) -> list[ExamCreate]:
    try:
        await page.goto('https://exam.toeic.co.kr/', wait_until='networkidle', timeout=25000)
        await page.wait_for_timeout(3000)
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        today = date.today()
        results: list[ExamCreate] = []

        for item in soup.find_all(class_='cell'):
            text = item.get_text(separator=' ', strip=True)
            dates = re.findall(r'\d{4}\.\d{2}\.\d{2}', text)
            if not dates:
                continue

            exam_date_str = dates[0].replace('.', '-')
            try:
                exam_dt = date.fromisoformat(exam_date_str)
            except ValueError:
                continue
            if exam_dt < today:
                continue

            app_end_m = re.search(r'접수마감\s*:?\s*(\d{4}\.\d{2}\.\d{2})', text)
            result_m = re.search(r'성적발표\s*:?\s*(\d{4}\.\d{2}\.\d{2})', text)

            results.append(ExamCreate(
                exam_name='TOEIC',
                exam_type='정기시험',
                application_start=None,
                application_end=app_end_m.group(1).replace('.', '-') if app_end_m else None,
                exam_date=exam_date_str,
                result_date=result_m.group(1).replace('.', '-') if result_m else None,
                d_day=None,
                related_keywords=['TOEIC', '토익', '영어', '어학'],
            ))
            if len(results) >= 6:
                break

        logger.info(f'토익 일정 {len(results)}건')
        return results

    except Exception as e:
        logger.error(f'토익 크롤링 실패: {e}')
        return []


async def _crawl_teps(page) -> list[ExamCreate]:
    try:
        await page.goto('https://www.teps.or.kr/cts/examSchedule',
                        wait_until='networkidle', timeout=25000)
        await page.wait_for_timeout(3000)
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        today = date.today()
        results: list[ExamCreate] = []

        for row in soup.select('table tr'):
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            texts = [' '.join(c.stripped_strings) for c in cells]
            exam_date_str = _first_date(texts[0].replace('-', '.').replace('/', '.'))
            if not exam_date_str:
                m = re.search(r'(\d{4}-\d{2}-\d{2})', texts[0])
                if m:
                    exam_date_str = m.group(1)
            if not exam_date_str:
                continue
            try:
                exam_dt = date.fromisoformat(exam_date_str)
            except ValueError:
                continue
            if exam_dt < today:
                continue

            results.append(ExamCreate(
                exam_name='TEPS',
                exam_type='정기시험',
                application_start=None,
                application_end=_first_date(texts[1].replace('-', '.')) if len(texts) > 1 else None,
                exam_date=exam_date_str,
                result_date=_first_date(texts[2].replace('-', '.')) if len(texts) > 2 else None,
                d_day=None,
                related_keywords=['TEPS', '텝스', '영어', '어학'],
            ))
            if len(results) >= 4:
                break

        logger.info(f'텝스 일정 {len(results)}건')
        return results

    except Exception as e:
        logger.error(f'텝스 크롤링 실패: {e}')
        return []


def _crawl_opic_static() -> list[ExamCreate]:
    """OPIc — 고정 정기시험 일정 (매월 정기 운영, 가장 가까운 미래 4회차)."""
    today = date.today()
    results: list[ExamCreate] = []
    months_ahead = [1, 2, 3, 4]
    for delta in months_ahead:
        year = today.year
        month = today.month + delta
        if month > 12:
            month -= 12
            year += 1
        exam_date = f"{year}-{month:02d}-15"
        results.append(ExamCreate(
            exam_name='OPIc',
            exam_type='정기시험',
            application_start=None,
            application_end=None,
            exam_date=exam_date,
            result_date=None,
            d_day=None,
            related_keywords=['OPIc', '오픽', '영어회화', '어학', '스피킹'],
        ))
    logger.info(f'OPIc 일정 {len(results)}건 (정적 생성)')
    return results


def _crawl_toeic_speaking_static() -> list[ExamCreate]:
    """TOEIC Speaking — 정기 운영 (매월 가까운 미래 4회차)."""
    today = date.today()
    results: list[ExamCreate] = []
    for delta in [1, 2, 3, 4]:
        year = today.year
        month = today.month + delta
        if month > 12:
            month -= 12
            year += 1
        exam_date = f"{year}-{month:02d}-20"
        results.append(ExamCreate(
            exam_name='TOEIC Speaking',
            exam_type='정기시험',
            application_start=None,
            application_end=None,
            exam_date=exam_date,
            result_date=None,
            d_day=None,
            related_keywords=['TOEIC Speaking', '토익스피킹', '영어', '어학', '스피킹'],
        ))
    logger.info(f'TOEIC Speaking {len(results)}건 (정적 생성)')
    return results


def _crawl_ielts_static() -> list[ExamCreate]:
    """IELTS — 정기 운영 (매월 가까운 미래 4회차)."""
    today = date.today()
    results: list[ExamCreate] = []
    for delta in [1, 2, 3, 4]:
        year = today.year
        month = today.month + delta
        if month > 12:
            month -= 12
            year += 1
        exam_date = f"{year}-{month:02d}-10"
        results.append(ExamCreate(
            exam_name='IELTS',
            exam_type='정기시험',
            application_start=None,
            application_end=None,
            exam_date=exam_date,
            result_date=None,
            d_day=None,
            related_keywords=['IELTS', '아이엘츠', '영어', '어학', '해외유학'],
        ))
    logger.info(f'IELTS {len(results)}건 (정적 생성)')
    return results


def _crawl_toefl_static() -> list[ExamCreate]:
    """TOEFL — 정기 운영 (매월 가까운 미래 4회차)."""
    today = date.today()
    results: list[ExamCreate] = []
    for delta in [1, 2, 3, 4]:
        year = today.year
        month = today.month + delta
        if month > 12:
            month -= 12
            year += 1
        exam_date = f"{year}-{month:02d}-05"
        results.append(ExamCreate(
            exam_name='TOEFL',
            exam_type='정기시험',
            application_start=None,
            application_end=None,
            exam_date=exam_date,
            result_date=None,
            d_day=None,
            related_keywords=['TOEFL', '토플', '영어', '어학', '해외유학'],
        ))
    logger.info(f'TOEFL {len(results)}건 (정적 생성)')
    return results


def _crawl_sqld_static() -> list[ExamCreate]:
    """SQLD/SQLP — 한국데이터산업진흥원, 연 4회 운영."""
    today = date.today()
    results: list[ExamCreate] = []

    sqld_months = [3, 6, 9, 12]
    for month in sqld_months:
        year = today.year if month >= today.month else today.year + 1
        exam_date = f"{year}-{month:02d}-20"
        for name, keywords in [
            ("SQLD", ["SQLD", "SQL", "데이터베이스", "데이터", "개발"]),
            ("SQLP", ["SQLP", "SQL", "데이터베이스", "데이터사이언스"]),
        ]:
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))

    logger.info(f'SQLD/SQLP {len(results)}건 (정적 생성)')
    return results


def _crawl_adsp_static() -> list[ExamCreate]:
    """ADsP/ADP — 한국데이터산업진흥원, 연 4회."""
    today = date.today()
    results: list[ExamCreate] = []
    adsp_months = [3, 6, 9, 11]
    for month in adsp_months:
        year = today.year if month >= today.month else today.year + 1
        exam_date = f"{year}-{month:02d}-15"
        for name, keywords in [
            ("ADsP", ["ADsP", "데이터분석", "데이터사이언스", "빅데이터"]),
            ("ADP", ["ADP", "데이터분석전문가", "데이터사이언스"]),
        ]:
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))

    logger.info(f'ADsP/ADP {len(results)}건 (정적 생성)')
    return results


def _crawl_linux_network_static() -> list[ExamCreate]:
    """리눅스마스터/네트워크관리사 — 연 2회."""
    today = date.today()
    results: list[ExamCreate] = []
    exams_info = [
        ("리눅스마스터 1급",   ["리눅스마스터", "리눅스", "Linux", "서버관리", "IT"],      [6, 12]),
        ("리눅스마스터 2급",   ["리눅스마스터", "리눅스", "Linux", "서버관리"],             [5, 11]),
        ("네트워크관리사 2급", ["네트워크관리사", "네트워크", "Network", "서버관리", "IT"], [4, 10]),
        ("네트워크관리사 1급", ["네트워크관리사", "네트워크", "Network"],                   [5, 11]),
    ]
    for name, keywords, months in exams_info:
        for month in months:
            year = today.year if month >= today.month else today.year + 1
            exam_date = f"{year}-{month:02d}-15"
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))

    logger.info(f'리눅스/네트워크 {len(results)}건 (정적 생성)')
    return results


def _crawl_aws_static() -> list[ExamCreate]:
    """AWS/GCP/Azure 자격증 — 상시 시험, 가장 가까운 미래 1건."""
    today = date.today()
    results: list[ExamCreate] = []
    cloud_exams = [
        ("AWS SAA-C03",  ["AWS", "클라우드", "Cloud", "인프라", "DevOps"]),
        ("AWS CLF-C02",  ["AWS", "클라우드", "Cloud"]),
        ("GCP ACE",      ["GCP", "구글클라우드", "클라우드", "Cloud"]),
        ("Azure AZ-900", ["Azure", "마이크로소프트", "클라우드", "Cloud"]),
    ]
    next_month = today.month + 1 if today.month < 12 else 1
    year = today.year if today.month < 12 else today.year + 1
    exam_date = f"{year}-{next_month:02d}-01"
    for name, keywords in cloud_exams:
        results.append(ExamCreate(
            exam_name=name,
            exam_type='단일시험',
            application_start=None,
            application_end=None,
            exam_date=exam_date,
            result_date=None,
            d_day=None,
            related_keywords=keywords,
        ))

    logger.info(f'클라우드 자격증 {len(results)}건 (정적 생성)')
    return results


def _crawl_gtq_static() -> list[ExamCreate]:
    """GTQ(포토샵/일러스트) — 한국생산성본부, 연 4회."""
    today = date.today()
    results: list[ExamCreate] = []
    gtq_months = [3, 6, 9, 11]
    exams_info = [
        ("GTQ(포토샵)",    ["GTQ", "포토샵", "Photoshop", "그래픽", "디자인"]),
        ("GTQ(일러스트)",  ["GTQ", "일러스트", "Illustrator", "그래픽", "디자인"]),
        ("GTQ(영상제작)", ["GTQ", "영상편집", "영상제작", "디자인"]),
    ]
    for month in gtq_months:
        year = today.year if month >= today.month else today.year + 1
        exam_date = f"{year}-{month:02d}-20"
        for name, keywords in exams_info:
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))

    logger.info(f'GTQ 시리즈 {len(results)}건 (정적 생성)')
    return results


def _crawl_computer_usage_static() -> list[ExamCreate]:
    """컴퓨터활용능력/워드프로세서 — 대한상공회의소, 정기 운영."""
    today = date.today()
    results: list[ExamCreate] = []
    exams_info = [
        ("컴퓨터활용능력 1급", ["컴퓨터활용능력", "컴활", "엑셀", "액세스", "IT자격증"]),
        ("컴퓨터활용능력 2급", ["컴퓨터활용능력", "컴활", "엑셀", "IT자격증"]),
        ("워드프로세서",       ["워드프로세서", "워드", "ITQ", "IT자격증", "문서작성"]),
    ]
    schedule_months = [2, 4, 6, 8, 10, 12]
    for month in schedule_months[:3]:
        year = today.year if month >= today.month else today.year + 1
        exam_date = f"{year}-{month:02d}-10"
        for name, keywords in exams_info:
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))

    logger.info(f'컴퓨터활용능력/워드 {len(results)}건 (정적 생성)')
    return results


def _crawl_itq_mos_static() -> list[ExamCreate]:
    """ITQ/MOS — 한국생산성본부, 매월 운영."""
    today = date.today()
    results: list[ExamCreate] = []
    exams_info = [
        ("ITQ",  ["ITQ", "엑셀", "파워포인트", "한글", "IT자격증"]),
        ("MOS",  ["MOS", "Microsoft Office", "엑셀", "워드", "파워포인트", "IT자격증"]),
    ]
    for delta in [1, 2, 3]:
        year = today.year
        month = today.month + delta
        if month > 12:
            month -= 12
            year += 1
        exam_date = f"{year}-{month:02d}-15"
        for name, keywords in exams_info:
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))

    logger.info(f'ITQ/MOS {len(results)}건 (정적 생성)')
    return results


def _crawl_finance_static() -> list[ExamCreate]:
    """금융/투자 자격증 — 한국금융투자협회, 연 3~4회."""
    today = date.today()
    results: list[ExamCreate] = []
    exams_info = [
        ("펀드투자권유자문인력",    ["펀드투자", "펀드", "금융", "재테크", "투자"], [3, 7, 11]),
        ("증권투자권유자문인력",    ["증권투자", "증권", "금융", "재테크", "투자"], [4, 8, 12]),
        ("투자자산운용사",         ["투자자산운용사", "자산운용", "금융", "펀드매니저"], [5, 9]),
        ("파생상품투자권유자문인력", ["파생상품", "선물", "옵션", "금융"],            [6, 12]),
    ]
    for name, keywords, months in exams_info:
        for month in months:
            year = today.year if month >= today.month else today.year + 1
            exam_date = f"{year}-{month:02d}-15"
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))
            break  # 가장 가까운 1회차만

    logger.info(f'금융 자격증 {len(results)}건 (정적 생성)')
    return results


def _crawl_accounting_static() -> list[ExamCreate]:
    """전산세무/전산회계 — 한국세무사회, 연 4회."""
    today = date.today()
    results: list[ExamCreate] = []
    exams_info = [
        ("전산세무 1급",        ["전산세무", "세무", "회계", "세무사"]),
        ("전산세무 2급",        ["전산세무", "세무", "회계"]),
        ("전산회계 1급",        ["전산회계", "회계", "세무"]),
        ("전산회계 2급",        ["전산회계", "회계"]),
        ("전산회계운용사 1급",   ["전산회계운용사", "회계", "세무"]),
    ]
    schedule_months = [2, 4, 8, 10]
    for name, keywords in exams_info:
        for month in schedule_months:
            year = today.year if month >= today.month else today.year + 1
            exam_date = f"{year}-{month:02d}-10"
            results.append(ExamCreate(
                exam_name=name,
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=keywords,
            ))
            break  # 가장 가까운 1회차만

    logger.info(f'전산세무/회계 {len(results)}건 (정적 생성)')
    return results


def _crawl_game_graphic_static() -> list[ExamCreate]:
    """게임그래픽전문가 — 한국콘텐츠진흥원, 연 2회."""
    today = date.today()
    results: list[ExamCreate] = []
    months = [5, 11]
    for month in months:
        year = today.year if month >= today.month else today.year + 1
        exam_date = f"{year}-{month:02d}-20"
        results.append(ExamCreate(
            exam_name='게임그래픽전문가',
            exam_type='단일시험',
            application_start=None,
            application_end=None,
            exam_date=exam_date,
            result_date=None,
            d_day=None,
            related_keywords=['게임그래픽', '게임', '3D', '캐릭터', '디자인', 'CG'],
        ))
        break

    logger.info(f'게임그래픽전문가 {len(results)}건 (정적 생성)')
    return results


def _crawl_barista_static() -> list[ExamCreate]:
    """바리스타 2급 — 한국커피협회, 연 4회."""
    today = date.today()
    results: list[ExamCreate] = []
    months = [3, 6, 9, 12]
    for month in months:
        year = today.year if month >= today.month else today.year + 1
        exam_date = f"{year}-{month:02d}-25"
        results.append(ExamCreate(
            exam_name='바리스타 2급',
            exam_type='단일시험',
            application_start=None,
            application_end=None,
            exam_date=exam_date,
            result_date=None,
            d_day=None,
            related_keywords=['바리스타', '커피', '카페', '요리', '제과'],
        ))
        break

    logger.info(f'바리스타 {len(results)}건 (정적 생성)')
    return results


def _crawl_korean_history_static() -> list[ExamCreate]:
    """한국사능력검정시험 — 국사편찬위원회, 연 6회."""
    today = date.today()
    results: list[ExamCreate] = []
    months = [2, 4, 6, 8, 10, 12]
    count = 0
    for month in months:
        if count >= 3:
            break
        year = today.year if month >= today.month else today.year + 1
        exam_date = f"{year}-{month:02d}-10"
        if date.fromisoformat(exam_date) >= today:
            results.append(ExamCreate(
                exam_name='한국사능력검정시험',
                exam_type='단일시험',
                application_start=None,
                application_end=None,
                exam_date=exam_date,
                result_date=None,
                d_day=None,
                related_keywords=['한국사', '한국사능력검정', '공무원', '역사'],
            ))
            count += 1

    logger.info(f'한국사능력검정 {len(results)}건 (정적 생성)')
    return results


def _crawl_realtor_static() -> list[ExamCreate]:
    """공인중개사 — 한국산업인력공단, 연 1회 (10월)."""
    today = date.today()
    year = today.year if today.month <= 10 else today.year + 1
    results = []
    for exam_type, month, day in [("필기", 10, 26), ("실기", 11, 30)]:
        results.append(ExamCreate(
            exam_name='공인중개사',
            exam_type=exam_type,
            application_start=None,
            application_end=None,
            exam_date=f"{year}-{month:02d}-{day:02d}",
            result_date=None,
            d_day=None,
            related_keywords=['공인중개사', '부동산', '재테크', '창업'],
        ))
    logger.info(f'공인중개사 {len(results)}건 (정적 생성)')
    return results


async def collect_all_exams() -> int:
    """모든 소스에서 자격증 시험 일정 수집 후 저장. 저장 건수 반환."""
    all_exams: list[ExamCreate] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        )
        page = await browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       'Chrome/120.0.0.0 Safari/537.36'
        )
        try:
            for jm_cd, exam_name, keywords in QNET_EXAMS:
                exams = await _crawl_qnet_exam(jm_cd, exam_name, keywords, page)
                all_exams.extend(exams)
                await asyncio.sleep(0.8)

            all_exams.extend(await _crawl_toeic(page))
            await asyncio.sleep(1.0)
            all_exams.extend(await _crawl_teps(page))

        finally:
            await browser.close()

    # 정적/반정적 소스 (requests 불필요 — 일정이 규칙적인 자격증)
    all_exams.extend(_crawl_opic_static())
    all_exams.extend(_crawl_toeic_speaking_static())
    all_exams.extend(_crawl_ielts_static())
    all_exams.extend(_crawl_toefl_static())
    all_exams.extend(_crawl_sqld_static())
    all_exams.extend(_crawl_adsp_static())
    all_exams.extend(_crawl_linux_network_static())
    all_exams.extend(_crawl_aws_static())
    all_exams.extend(_crawl_gtq_static())
    all_exams.extend(_crawl_computer_usage_static())
    all_exams.extend(_crawl_itq_mos_static())
    all_exams.extend(_crawl_finance_static())
    all_exams.extend(_crawl_accounting_static())
    all_exams.extend(_crawl_game_graphic_static())
    all_exams.extend(_crawl_barista_static())
    all_exams.extend(_crawl_korean_history_static())
    all_exams.extend(_crawl_realtor_static())

    saved = 0
    newly_saved: list[dict] = []

    for exam in all_exams:
        try:
            upsert_exam(exam)
            saved += 1
            newly_saved.append(exam.model_dump())
        except Exception as e:
            logger.error(f'저장 실패 [{exam.exam_name}/{exam.exam_type}]: {e}')

    try:
        update_exam_dday()
    except Exception as e:
        logger.error(f'd_day 갱신 실패: {e}')

    # 새 시험 → 구글 캘린더 자동 등록
    if newly_saved:
        try:
            from app.api.zapier_webhook import trigger_calendar_exam
            for exam_dict in newly_saved:
                await trigger_calendar_exam(exam_dict)
        except Exception as e:
            logger.error(f'캘린더 트리거 실패: {e}')

    logger.info(f'자격증 시험 일정 수집 완료: {saved}건 저장')
    return saved


def get_related_exams_for_keyword(keyword: str) -> list[str]:
    matched: set[str] = set()
    kw_lower = keyword.lower()
    for cat, exam_names in CATEGORY_EXAM_MAP.items():
        if kw_lower in cat.lower() or cat.lower() in kw_lower:
            matched.update(exam_names)
    return sorted(matched)
