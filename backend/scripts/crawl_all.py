"""전체 플랫폼 크롤러 일괄 실행 스크립트.

사용법:
    python3 scripts/crawl_all.py                  # 전체 실행
    python3 scripts/crawl_all.py --only inflearn  # 특정 플랫폼만
    python3 scripts/crawl_all.py --skip udemy     # 특정 플랫폼 건너뜀
    python3 scripts/crawl_all.py --from hackers   # 특정 플랫폼부터 재시작

특징:
    - 플랫폼별 독립 실행 — 하나 실패해도 다음 플랫폼 계속 진행
    - 플랫폼별 소요시간/수집건수 요약 출력
    - logs/crawl_YYYYMMDD_HHMMSS.log 에 전체 로그 저장
"""
import asyncio
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase_client import supabase
from app.utils.logger import logger

# ── 크롤러 목록 (순서 = 실행 순서) ──────────────────────────
CRAWLERS = [
    # IT/개발
    {
        "name": "inflearn",
        "label": "인프런",
        "module": "app.crawlers.inflearn",
        "class": "InflearnCrawler",
        "category": "IT/개발",
    },
    {
        "name": "udemy",
        "label": "유데미",
        "module": "app.crawlers.udemy",
        "class": "UdemyCrawler",
        "category": "IT/개발+전반",
    },
    {
        "name": "opentutorials",
        "label": "생활코딩",
        "module": "app.crawlers.opentutorials",
        "class": "OpentutorialsCrawler",
        "category": "IT/개발(무료)",
    },
    {
        "name": "nomadcoder",
        "label": "노마드코더",
        "module": "app.crawlers.opentutorials",
        "class": "NomadcoderCrawler",
        "category": "IT/개발",
    },
    {
        "name": "codeit",
        "label": "코드잇",
        "module": "app.crawlers.codeit",
        "class": "CodeitCrawler",
        "category": "IT/개발",
    },
    {
        "name": "fastcampus",
        "label": "패스트캠퍼스",
        "module": "app.crawlers.fastcampus",
        "class": "FastcampusCrawler",
        "category": "IT/개발",
    },
    {
        "name": "sparta",
        "label": "스파르타코딩클럽",
        "module": "app.crawlers.sparta_zerobase",
        "class": "SpartaCrawler",
        "category": "IT/개발",
    },
    {
        "name": "zerobase",
        "label": "제로베이스",
        "module": "app.crawlers.sparta_zerobase",
        "class": "ZerobaseCrawler",
        "category": "IT/개발",
    },
    # 공무원/자격증
    {
        "name": "hackers",
        "label": "해커스",
        "module": "app.crawlers.hackers",
        "class": "HackersCrawler",
        "category": "공무원/어학/자격증",
    },
    {
        "name": "eduwill",
        "label": "에듀윌",
        "module": "app.crawlers.eduwill",
        "class": "EduwillCrawler",
        "category": "공무원/자격증",
    },
    {
        "name": "megastudy",
        "label": "메가스터디",
        "module": "app.crawlers.megastudy",
        "class": "MegastudyCrawler",
        "category": "수능/공무원",
    },
    # 어학
    {
        "name": "siwonschool",
        "label": "시원스쿨",
        "module": "app.crawlers.siwonschool",
        "class": "SiwonschoolCrawler",
        "category": "어학",
    },
    {
        "name": "yanadoo",
        "label": "야나두",
        "module": "app.crawlers.yanadoo",
        "class": "YanadooCrawler",
        "category": "어학",
    },
    {
        "name": "ybm",
        "label": "YBM",
        "module": "app.crawlers.yanadoo",
        "class": "YBMCrawler",
        "category": "어학",
    },
    {
        "name": "santa_toeic",
        "label": "산타토익",
        "module": "app.crawlers.yanadoo",
        "class": "SantaToeicCrawler",
        "category": "어학",
    },
    # 수능
    {
        "name": "ebsi",
        "label": "EBSi",
        "module": "app.crawlers.ebs",
        "class": "EBSiCrawler",
        "category": "수능(무료)",
    },
    {
        "name": "etoos",
        "label": "이투스",
        "module": "app.crawlers.ebs",
        "class": "EtoossCrawler",
        "category": "수능",
    },
    # 디자인/창작
    {
        "name": "class101",
        "label": "클래스101",
        "module": "app.crawlers.class101",
        "class": "Class101Crawler",
        "category": "디자인/창작/취미",
    },
    {
        "name": "coloso",
        "label": "콜로소",
        "module": "app.crawlers.coloso",
        "class": "ColosoCrawler",
        "category": "디자인/창작/비즈니스",
    },
    {
        "name": "bearyu",
        "label": "베어유",
        "module": "app.crawlers.bearyu_publy",
        "class": "BearYuCrawler",
        "category": "디자인/창작",
    },
    # 자기계발/인사이트
    {
        "name": "publy",
        "label": "퍼블리",
        "module": "app.crawlers.bearyu_publy",
        "class": "PublyCrawler",
        "category": "자기계발/인사이트",
    },
    {
        "name": "folin",
        "label": "폴인",
        "module": "app.crawlers.bearyu_publy",
        "class": "FoleinCrawler",
        "category": "자기계발/인사이트",
    },
    # 유튜브 무료 강의 (예산 없음 추천용)
    {
        "name": "youtube",
        "label": "유튜브",
        "module": "app.crawlers.youtube_lectures",
        "class": "YoutubeLectureCrawler",
        "category": "무료(유튜브)",
    },
]


def get_db_counts() -> dict:
    lectures = supabase.table("lectures").select("id", count="exact").execute().count
    instructors = supabase.table("instructors").select("id", count="exact").execute().count
    return {"lectures": lectures, "instructors": instructors}


async def run_crawler(cfg: dict) -> tuple[int, str]:
    """크롤러 하나 실행. (수집건수, 상태) 반환."""
    import importlib
    try:
        module = importlib.import_module(cfg["module"])
        cls = getattr(module, cfg["class"])
        crawler = cls()
        result = await crawler.crawl()
        return len(result), "✅ 완료"
    except Exception as e:
        logger.error(f"{cfg['label']} 크롤러 실패: {e}")
        return 0, f"❌ 실패: {e}"


async def main():
    parser = argparse.ArgumentParser(description="전체 플랫폼 크롤러 실행")
    parser.add_argument("--only", nargs="+", metavar="NAME", help="이 플랫폼만 실행 (예: inflearn udemy)")
    parser.add_argument("--skip", nargs="+", metavar="NAME", help="이 플랫폼 건너뜀")
    parser.add_argument("--from", dest="from_platform", metavar="NAME", help="이 플랫폼부터 재시작")
    args = parser.parse_args()

    # 실행할 크롤러 필터링
    crawlers_to_run = CRAWLERS[:]
    if args.only:
        crawlers_to_run = [c for c in crawlers_to_run if c["name"] in args.only]
    if args.skip:
        crawlers_to_run = [c for c in crawlers_to_run if c["name"] not in args.skip]
    if args.from_platform:
        names = [c["name"] for c in crawlers_to_run]
        if args.from_platform in names:
            start_idx = names.index(args.from_platform)
            crawlers_to_run = crawlers_to_run[start_idx:]

    if not crawlers_to_run:
        print("실행할 크롤러가 없습니다.")
        return

    total_start = time.time()
    start_counts = get_db_counts()

    print(f"\n{'='*60}")
    print(f" 크롤링 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 실행 플랫폼: {len(crawlers_to_run)}개")
    print(f" 현재 DB: lectures={start_counts['lectures']}건, instructors={start_counts['instructors']}명")
    print(f"{'='*60}\n")

    results = []
    for i, cfg in enumerate(crawlers_to_run, 1):
        print(f"[{i}/{len(crawlers_to_run)}] {cfg['label']} ({cfg['category']}) 시작...")
        t0 = time.time()
        count, status = await run_crawler(cfg)
        elapsed = time.time() - t0
        results.append({
            "name": cfg["name"],
            "label": cfg["label"],
            "count": count,
            "status": status,
            "elapsed": elapsed,
        })
        print(f"  → {status} | {count}건 | {elapsed:.0f}초\n")

    # 최종 요약
    end_counts = get_db_counts()
    total_elapsed = time.time() - total_start

    print(f"\n{'='*60}")
    print(f" 크롤링 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 총 소요시간: {total_elapsed/60:.1f}분")
    print(f"{'='*60}")
    print(f"\n{'플랫폼':<20} {'건수':>6} {'시간':>6}  상태")
    print("-" * 55)
    for r in results:
        print(f"  {r['label']:<18} {r['count']:>6}건  {r['elapsed']:>5.0f}초  {r['status']}")
    print("-" * 55)
    print(f"\n=== 최종 DB 현황 ===")
    print(f"  lectures:    {start_counts['lectures']}건 → {end_counts['lectures']}건 (+{end_counts['lectures'] - start_counts['lectures']}건)")
    print(f"  instructors: {start_counts['instructors']}명 → {end_counts['instructors']}명 (+{end_counts['instructors'] - start_counts['instructors']}명)")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
