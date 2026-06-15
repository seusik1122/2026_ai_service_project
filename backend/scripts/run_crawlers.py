"""
딸깍 한 번으로 전체 크롤러 실행.

사용법:
    python scripts/run_crawlers.py              # 전체 실행
    python scripts/run_crawlers.py --resume     # 실패한 것만 재시도
    python scripts/run_crawlers.py --only inflearn hackers  # 특정 크롤러만

진행상황은 logs/crawl_progress.json 에 저장 → 중간에 죽어도 이어서 재개 가능
로그는 logs/crawl_YYYYMMDD_HHMMSS.log 에 저장
"""
import sys
import json
import asyncio
import argparse
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

import logging

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

PROGRESS_FILE = LOG_DIR / "crawl_progress.json"
LOG_FILE = LOG_DIR / f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ─── 크롤러 등록 ───────────────────────────────────────────────
# (이름, 임포트경로, 클래스명) — 새 크롤러 추가 시 여기만 수정
CRAWLERS = [
    # Playwright (JS 렌더링)
    ("inflearn",      "app.crawlers.inflearn",      "InflearnCrawler"),
    ("udemy",         "app.crawlers.udemy",         "UdemyCrawler"),
    ("siwonschool",   "app.crawlers.siwonschool",   "SiwonschoolCrawler"),
    ("hackers",       "app.crawlers.hackers",       "HackersCrawler"),
    ("eduwill",       "app.crawlers.eduwill",       "EduwillCrawler"),
    ("opentutorials", "app.crawlers.opentutorials", "OpentutorialsCrawler"),
    ("nomadcoder",    "app.crawlers.opentutorials", "NomadcoderCrawler"),
]

# ─── 진행상황 저장/로드 ────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

# ─── 크롤러 실행 ──────────────────────────────────────────────

async def run_one(name: str, module_path: str, class_name: str) -> dict:
    """단일 크롤러 실행. 결과 dict 반환."""
    import importlib
    try:
        module = importlib.import_module(module_path)
        CrawlerClass = getattr(module, class_name)
        crawler = CrawlerClass()
        logger.info(f"━━━ [{name}] 시작 ━━━")
        start = datetime.now()
        items = await crawler.crawl()
        elapsed = (datetime.now() - start).seconds
        logger.info(f"━━━ [{name}] 완료: {len(items)}건 ({elapsed}초) ━━━")
        return {"status": "ok", "count": len(items), "elapsed": elapsed}
    except Exception as e:
        logger.error(f"━━━ [{name}] 실패: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "error": str(e), "count": 0}

async def run_all(targets: list[tuple], resume_only: bool = False):
    progress = load_progress()
    total_collected = 0
    failed = []

    for name, module_path, class_name in targets:
        # --resume 모드: 이미 성공한 것은 건너뜀
        if resume_only and progress.get(name, {}).get("status") == "ok":
            logger.info(f"[{name}] 이미 완료 — 건너뜀")
            total_collected += progress[name].get("count", 0)
            continue

        result = await run_one(name, module_path, class_name)
        progress[name] = {"timestamp": datetime.now().isoformat(), **result}
        save_progress(progress)  # 크롤러 하나 끝날 때마다 저장
        total_collected += result["count"]

        if result["status"] == "error":
            failed.append(name)

        # 사이트 간 딜레이 (차단 방지)
        await asyncio.sleep(3)

    # ─── 구글 후기 수집 ───────────────────────────────────────
    logger.info("\n━━━ [google_reviews] 구글 블로그 후기 수집 시작 ━━━")
    try:
        from app.collectors.google_review_crawler import GoogleReviewCrawler
        review_count = await GoogleReviewCrawler().crawl()
        logger.info(f"━━━ [google_reviews] 완료: {review_count}건 ━━━")
    except Exception as e:
        logger.error(f"━━━ [google_reviews] 실패: {e}")

    # ─── 최종 요약 ────────────────────────────────────────────
    logger.info("\n" + "=" * 50)
    logger.info(f"전체 크롤링 완료: 총 {total_collected}건 수집")
    logger.info(f"성공: {len(targets) - len(failed)}개 / 실패: {len(failed)}개")
    if failed:
        logger.info(f"실패 크롤러: {', '.join(failed)}")
        logger.info(f"재시도: python scripts/run_crawlers.py --resume")
    logger.info(f"로그 파일: {LOG_FILE}")
    logger.info(f"진행상황: {PROGRESS_FILE}")
    logger.info("=" * 50)

    # DB 현황 출력
    try:
        from app.db.supabase_client import supabase
        for table in ["lectures", "reviews", "instructors"]:
            count = supabase.table(table).select("id", count="exact").execute().count
            logger.info(f"  DB {table}: {count}건")
    except Exception as e:
        logger.error(f"DB 현황 조회 실패: {e}")

# ─── 진입점 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="전체 크롤러 실행")
    parser.add_argument("--resume", action="store_true", help="실패한 크롤러만 재시도")
    parser.add_argument("--only", nargs="+", metavar="NAME", help="특정 크롤러만 실행 (예: inflearn hackers)")
    args = parser.parse_args()

    targets = CRAWLERS
    if args.only:
        targets = [(n, m, c) for n, m, c in CRAWLERS if n in args.only]
        if not targets:
            print(f"알 수 없는 크롤러: {args.only}. 사용 가능: {[n for n,_,_ in CRAWLERS]}")
            sys.exit(1)

    logger.info(f"크롤링 시작: {[n for n,_,_ in targets]}개 크롤러")
    logger.info(f"로그: {LOG_FILE}")
    asyncio.run(run_all(targets, resume_only=args.resume))

if __name__ == "__main__":
    main()
