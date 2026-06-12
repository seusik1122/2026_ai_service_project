"""시연용 더미 데이터 시드 (명세서 4주차 '시연용 더미 데이터 30건 이상 준비').

크롤러/수집기가 쓰는 것과 동일한 queries 함수로 적재한다(스키마/인터페이스 변경 없음):
  - upsert_lecture / upsert_instructor / insert_review / upsert_exam
후기는 명세 흐름대로 미분석 원본(is_ad=False, sentiment=NULL)으로 넣어
B의 AI 파이프라인(ad_filter → sentiment → trust_score)이 처리하도록 남겨둔다.

실행:  python scripts/seed_demo_data.py
재실행 안전(upsert: url / name+platform / original_url / exam_name+exam_type 기준 멱등).
"""
import sys
from pathlib import Path

# scripts/ 에서 실행해도 app 패키지를 찾도록 백엔드 루트를 path 에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.supabase_client import supabase
from app.db.models import LectureCreate, ReviewCreate, ExamCreate
from app.db.queries import (
    upsert_lecture,
    upsert_instructor,
    insert_review,
    upsert_exam,
    update_exam_dday,
)

# ── 강사 (name, platform) ────────────────────────────────────────────
INSTRUCTORS = [
    ("김영한", "inflearn"),
    ("박재성", "inflearn"),
    ("조코딩", "inflearn"),
    ("이고잉", "inflearn"),
    ("데이비드조", "inflearn"),
    ("션", "class101"),
    ("빠니", "class101"),
    ("김지훈", "fastcampus"),
    ("한정수", "fastcampus"),
    ("전한길", "fastcampus"),
    ("김민수", "kmooc"),
    ("이수진", "kmooc"),
]


def _lec(platform, title, instructor, category, price, rating, students, slug,
         tags, is_free=False):
    return {
        "platform": platform,
        "title": title,
        "instructor_name": instructor,
        "category": category,
        "price": price,
        "rating": rating,
        "student_count": students,
        "url": f"https://demo.seed/{platform}/{slug}",
        "thumbnail_url": f"https://demo.seed/thumb/{slug}.png",
        "tags": tags,
        "is_free": is_free,
    }


# ── 강의 32건 (IT/공무원/자격증/어학/디자인/공예 · 5개 플랫폼) ──────────────
LECTURES = [
    # 인프런 (IT)
    _lec("inflearn", "실전! 스프링 부트와 JPA 활용", "김영한", "IT", 99000, 4.9, 18200, "spring-jpa", ["Spring", "JPA", "백엔드"]),
    _lec("inflearn", "자바 ORM 표준 JPA 프로그래밍", "김영한", "IT", 88000, 4.8, 14300, "java-jpa", ["Java", "JPA"]),
    _lec("inflearn", "테스트 주도 개발 TDD 실전", "박재성", "IT", 110000, 4.7, 6700, "tdd", ["TDD", "테스트", "Java"]),
    _lec("inflearn", "클린 코드와 리팩터링", "박재성", "IT", 95000, 4.8, 8100, "clean-code", ["리팩터링", "OOP"]),
    _lec("inflearn", "노코드로 앱 만들기 입문", "조코딩", "IT", 0, 4.6, 23400, "nocode-app", ["노코드", "앱"], is_free=True),
    _lec("inflearn", "챗GPT API 활용 사이드프로젝트", "조코딩", "IT", 55000, 4.5, 9800, "chatgpt-api", ["GPT", "API"]),
    _lec("inflearn", "생활코딩 WEB 기초", "이고잉", "IT", 0, 4.7, 41200, "web-basic", ["HTML", "CSS", "입문"], is_free=True),
    _lec("inflearn", "토익 700+ 단기완성", "데이비드조", "어학", 66000, 4.4, 5300, "toeic-700", ["토익", "영어"]),
    _lec("inflearn", "비즈니스 영어 회화", "데이비드조", "어학", 72000, 4.3, 3100, "biz-english", ["영어", "회화"]),
    # 클래스101 (디자인/공예) — 로그인 벽 가격은 -1 정책
    _lec("class101", "아이패드 드로잉 클래스", "션", "디자인", -1, 4.8, None, "ipad-drawing", ["드로잉", "아이패드"]),
    _lec("class101", "프로크리에이트 캐릭터 일러스트", "션", "디자인", 159000, 4.7, None, "procreate-char", ["일러스트", "캐릭터"]),
    _lec("class101", "감성 캘리그라피 입문", "빠니", "공예", -1, 4.6, None, "calligraphy", ["캘리그라피", "손글씨"]),
    _lec("class101", "수채화로 그리는 일상", "빠니", "공예", 129000, 4.5, None, "watercolor", ["수채화", "취미"]),
    # 패스트캠퍼스 (IT/공무원)
    _lec("fastcampus", "데이터 엔지니어링 올인원", "김지훈", "IT", 599000, 4.6, 4200, "data-eng", ["SQL", "Airflow", "데이터"]),
    _lec("fastcampus", "빅데이터 파이프라인 구축", "김지훈", "IT", 540000, 4.5, 2600, "bigdata-pipe", ["Spark", "Kafka"]),
    _lec("fastcampus", "프론트엔드 마스터 React", "한정수", "IT", 480000, 4.7, 5900, "fe-react", ["React", "TypeScript"]),
    _lec("fastcampus", "Next.js 실전 프로젝트", "한정수", "IT", 460000, 4.6, 3300, "nextjs", ["Next.js", "프론트엔드"]),
    _lec("fastcampus", "공무원 한국사 기출 완성", "전한길", "공무원", 320000, 4.9, 12800, "history-gong", ["한국사", "공무원"]),
    _lec("fastcampus", "공무원 행정학 핵심정리", "전한길", "공무원", 280000, 4.7, 7400, "admin-gong", ["행정학", "공무원"]),
    # K-MOOC (무료, IT/자격증)
    _lec("kmooc", "파이썬 프로그래밍 입문", "김민수", "IT", 0, 4.5, 8800, "kmooc-python", ["Python", "입문"], is_free=True),
    _lec("kmooc", "인공지능 수학 기초", "김민수", "IT", 0, 4.4, 5200, "kmooc-aimath", ["AI", "수학"], is_free=True),
    _lec("kmooc", "정보처리기사 실기 특강", "이수진", "자격증", 0, 4.6, 6100, "kmooc-info", ["정보처리기사", "자격증"], is_free=True),
    _lec("kmooc", "컴퓨터활용능력 1급 핵심", "이수진", "자격증", 0, 4.3, 4400, "kmooc-comp", ["컴활", "자격증"], is_free=True),
    _lec("kmooc", "데이터 분석 입문", "김민수", "IT", 0, 4.5, 3900, "kmooc-da", ["데이터분석", "통계"], is_free=True),
    # 추가 IT/어학/자격증 강의로 30건 이상 확보
    _lec("inflearn", "도커와 쿠버네티스 입문", "박재성", "IT", 77000, 4.6, 9100, "docker-k8s", ["Docker", "K8s"]),
    _lec("inflearn", "알고리즘 코딩테스트 입문", "조코딩", "IT", 49000, 4.7, 15600, "algo-coding", ["알고리즘", "코테"]),
    _lec("fastcampus", "SQL 데이터 분석 부트캠프", "김지훈", "IT", 390000, 4.5, 4700, "sql-bootcamp", ["SQL", "분석"]),
    _lec("fastcampus", "공무원 영어 독해 전략", "전한길", "공무원", 250000, 4.4, 3800, "eng-gong", ["영어", "공무원"]),
    _lec("inflearn", "토익스피킹 레벨업", "데이비드조", "어학", 59000, 4.2, 2100, "toeic-speaking", ["토스", "영어"]),
    _lec("class101", "디지털 굿즈 제작 클래스", "빠니", "공예", 99000, 4.4, None, "digital-goods", ["굿즈", "디자인"]),
    _lec("kmooc", "자료구조와 알고리즘", "이수진", "IT", 0, 4.5, 5500, "kmooc-ds", ["자료구조", "CS"], is_free=True),
    _lec("inflearn", "스프링 시큐리티 완전정복", "김영한", "IT", 105000, 4.8, 7200, "spring-security", ["Spring", "보안"]),
]

# ── 후기 (미분석 원본: is_ad=False, sentiment=NULL) ─────────────────────
def _rev(instructor, source, content, slug):
    return ReviewCreate(
        instructor_name=instructor,
        platform_source=source,
        content=content,
        is_ad=False,
        original_url=f"https://demo.seed/review/{slug}",
    )


REVIEWS = [
    _rev("김영한", "naver_blog", "스프링 부트 강의 완강했어요. 실무에서 바로 쓸 수 있는 내용이라 만족합니다. 다만 초반 난이도가 조금 높아요.", "kyh-1"),
    _rev("김영한", "naver_cafe", "JPA 개념이 어려웠는데 이 강의로 확실히 잡았습니다. 설명이 깔끔해요.", "kyh-2"),
    _rev("김영한", "youtube_comment", "역시 김영한님 강의는 믿고 듣습니다. 퀄리티 최고", "kyh-3"),
    _rev("김영한", "naver_blog", "환급까지 받았네요. 비추할 이유가 없는 강의입니다.", "kyh-4"),
    _rev("박재성", "naver_blog", "TDD를 처음 배웠는데 실습 위주라 좋았어요. 과제가 빡세지만 그만큼 남는 게 많습니다.", "pjs-1"),
    _rev("박재성", "youtube_comment", "클린코드 강의 듣고 코드 보는 눈이 달라졌어요.", "pjs-2"),
    _rev("박재성", "naver_cafe", "리팩터링 파트는 조금 빠르게 지나가서 두 번 봤습니다.", "pjs-3"),
    _rev("조코딩", "youtube_comment", "노코드 강의 입문용으로 완벽해요. 비전공자도 따라갈 수 있음", "jcd-1"),
    _rev("조코딩", "naver_blog", "사이드 프로젝트 만들면서 배우니 재밌네요. 추천합니다.", "jcd-2"),
    _rev("조코딩", "naver_blog", "무료 강의인데 퀄리티가 유료급입니다. 감사합니다.", "jcd-3"),
    _rev("이고잉", "naver_cafe", "생활코딩은 입문자 바이블이죠. 웹 기초 다지기 좋아요.", "lgg-1"),
    _rev("이고잉", "youtube_comment", "설명이 친절해서 끝까지 들었습니다.", "lgg-2"),
    _rev("데이비드조", "naver_blog", "토익 700 목표였는데 한 달 만에 달성했어요. 핵심만 콕콕 짚어줍니다.", "dvd-1"),
    _rev("데이비드조", "naver_cafe", "회화 강의는 조금 기대 이하였어요. 분량이 적습니다.", "dvd-2"),
    _rev("션", "naver_blog", "아이패드 드로잉 처음인데 따라 그리니 결과물이 나와요. 뿌듯합니다.", "sean-1"),
    _rev("션", "youtube_comment", "브러시 설정까지 알려줘서 좋았어요.", "sean-2"),
    _rev("빠니", "naver_blog", "캘리그라피 손글씨 교정에 도움 많이 됐어요. 힐링됩니다.", "ppn-1"),
    _rev("빠니", "naver_cafe", "준비물이 생각보다 많이 들어요. 그래도 만족.", "ppn-2"),
    _rev("김지훈", "naver_blog", "데이터 엔지니어링 올인원 가성비 좋아요. Airflow 실습이 알찹니다.", "kjh-1"),
    _rev("김지훈", "youtube_comment", "현업자 입장에서 봐도 내용이 탄탄합니다.", "kjh-2"),
    _rev("김지훈", "naver_cafe", "분량이 방대해서 완강에 오래 걸렸지만 그만한 가치가 있어요.", "kjh-3"),
    _rev("한정수", "naver_blog", "React 마스터 강의 듣고 이직 성공했습니다. 강추!", "hjs-1"),
    _rev("한정수", "youtube_comment", "Next.js 실전 프로젝트 따라 만드니 포트폴리오가 채워지네요.", "hjs-2"),
    _rev("한정수", "naver_cafe", "기초가 부족하면 조금 버거울 수 있어요.", "hjs-3"),
    _rev("전한길", "naver_blog", "한국사는 역시 전한길입니다. 기출 분석이 미쳤어요.", "jhg-1"),
    _rev("전한길", "naver_cafe", "행정학 핵심정리 덕분에 점수 올렸습니다.", "jhg-2"),
    _rev("전한길", "youtube_comment", "동기부여까지 해주셔서 끝까지 완주했어요.", "jhg-3"),
    _rev("김민수", "naver_blog", "K-MOOC 무료 파이썬 강의 중 제일 깔끔합니다.", "kms-1"),
    _rev("김민수", "naver_cafe", "AI 수학 기초가 부족했는데 도움이 많이 됐어요.", "kms-2"),
    _rev("이수진", "naver_blog", "정보처리기사 실기 특강으로 한 번에 합격했습니다!", "lsj-1"),
    _rev("이수진", "youtube_comment", "컴활 1급 핵심만 정리해줘서 시간 절약했어요.", "lsj-2"),
    _rev("이수진", "naver_cafe", "무료 강의라 기대 안 했는데 알찼습니다.", "lsj-3"),
]

# ── 자격증 시험 일정 (현재 2026-05-30 기준 미래 일정) ──────────────────
EXAMS = [
    ExamCreate(exam_name="정보처리기사", exam_type="필기",
               application_start="2026-06-08", application_end="2026-06-12",
               exam_date="2026-07-05", result_date="2026-07-25",
               related_keywords=["정보처리기사", "자격증", "IT"]),
    ExamCreate(exam_name="정보처리기사", exam_type="실기",
               application_start="2026-08-03", application_end="2026-08-07",
               exam_date="2026-09-06", result_date="2026-09-26",
               related_keywords=["정보처리기사", "실기"]),
    ExamCreate(exam_name="컴퓨터활용능력 1급", exam_type="필기",
               application_start="2026-06-15", application_end="2026-06-19",
               exam_date="2026-06-27", result_date="2026-07-10",
               related_keywords=["컴활", "컴퓨터활용능력"]),
    ExamCreate(exam_name="컴퓨터활용능력 1급", exam_type="실기",
               application_start="2026-07-13", application_end="2026-07-17",
               exam_date="2026-08-08", result_date="2026-08-21",
               related_keywords=["컴활", "실기"]),
    ExamCreate(exam_name="SQLD", exam_type="필기",
               application_start="2026-07-20", application_end="2026-07-24",
               exam_date="2026-08-22", result_date="2026-09-11",
               related_keywords=["SQLD", "데이터", "자격증"]),
    ExamCreate(exam_name="토익", exam_type="필기",
               application_start="2026-06-01", application_end="2026-06-10",
               exam_date="2026-06-21", result_date="2026-07-01",
               related_keywords=["토익", "어학", "영어"]),
]


def _count(table: str) -> int:
    return supabase.table(table).select("id", count="exact").execute().count or 0


def main() -> None:
    print("=== 시연용 더미 데이터 시드 시작 ===")

    print("[강사] upsert_instructor")
    for name, platform in INSTRUCTORS:
        upsert_instructor(name, platform)
    print(f"  강사 {len(INSTRUCTORS)}명")

    print("[강의] upsert_lecture")
    for item in LECTURES:
        upsert_lecture(LectureCreate(**item))
    print(f"  강의 {len(LECTURES)}건")

    print("[후기] insert_review (미분석 원본)")
    for r in REVIEWS:
        insert_review(r)
    print(f"  후기 {len(REVIEWS)}건")

    print("[시험] upsert_exam")
    for e in EXAMS:
        upsert_exam(e)
    update_exam_dday()  # d_day 초기 계산
    print(f"  시험 {len(EXAMS)}건")

    print("\n=== Supabase 적재 확인 (count) ===")
    for t in ["instructors", "lectures", "reviews", "exams"]:
        print(f"  {t:12}: {_count(t)} rows")

    sample = supabase.table("exams").select("exam_name, exam_type, exam_date, d_day").order("d_day").limit(3).execute().data
    print("\n  가까운 시험 D-day 샘플:")
    for s in sample:
        print(f"    {s['exam_name']} {s['exam_type']} ({s['exam_date']}) → D-{s['d_day']}")

    print("\n=== 완료 ✅ ===")


if __name__ == "__main__":
    main()
