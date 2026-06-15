# APScheduler 기반 주기적 수집 스케줄러
# - 매일 자정: 플랫폼 크롤링(inflearn/class101/fastcampus) — class101 명세: 하루 1회 자정
# - 매일 00:05: 시험 D-day 갱신(update_exam_dday)
# - 매일 00:30 / 01:00: K-MOOC 강의 / 큐넷 시험일정 수집
# - 매일 02:00: 강사 후기 수집(네이버 + 유튜브)
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.crawlers.inflearn import InflearnCrawler
from app.crawlers.class101 import Class101Crawler
from app.crawlers.fastcampus import FastcampusCrawler
from app.collectors.naver_api import collect_naver_reviews
from app.collectors.youtube_api import collect_youtube_reviews
from app.collectors.kmooc_api import collect_kmooc_lectures
from app.collectors.qnet_api import collect_qnet_exams
from app.db.supabase_client import supabase
from app.db.queries import update_exam_dday
from app.utils.logger import logger
from app.api.zapier_webhook import trigger_dday_alerts, trigger_trust_score_alerts

scheduler = AsyncIOScheduler()

CRAWLER_CLASSES = (InflearnCrawler, Class101Crawler, FastcampusCrawler)


async def run_all_crawlers() -> None:
    """등록된 모든 플랫폼 크롤러를 순차 실행. 하나가 실패해도 나머지는 진행."""
    for crawler_cls in CRAWLER_CLASSES:
        try:
            await crawler_cls().crawl()
        except Exception as e:
            logger.error(f"크롤러 실패: {crawler_cls.__name__} — {e}")


def _review_target_instructors() -> list[str]:
    """크롤링된 lectures 에서 후기 수집 대상 강사명(중복 제거)을 추출."""
    try:
        rows = supabase.table("lectures").select("instructor_name").execute().data
    except Exception as e:
        logger.error(f"후기 대상 강사 조회 실패 — {e}")
        return []
    names = {r.get("instructor_name") for r in rows if r.get("instructor_name")}
    return sorted(names)


async def collect_all_reviews() -> None:
    """강사별 네이버·유튜브 후기 수집. 동기 수집기는 스레드로 돌려 루프 비차단."""
    for name in _review_target_instructors():
        try:
            await asyncio.to_thread(collect_naver_reviews, name)
            await asyncio.to_thread(collect_youtube_reviews, name)
        except Exception as e:
            logger.error(f"후기 수집 실패: {name} — {e}")


async def run_dday_and_notify() -> None:
    """D-day 갱신 후 D-7 이하 시험 Zapier 이메일 발송."""
    try:
        await asyncio.to_thread(update_exam_dday)
    except Exception as e:
        logger.error(f"D-day 갱신 실패: {e}")
    try:
        sent = await trigger_dday_alerts()
        logger.info(f"D-day 알림 발송: {sent}건")
    except Exception as e:
        logger.error(f"D-day 알림 실패: {e}")


async def run_trust_score_check() -> None:
    """주간 신뢰도 급변 강사 감지 → Zapier 이메일 발송."""
    try:
        sent = await trigger_trust_score_alerts()
        logger.info(f"신뢰도 급변 알림 발송: {sent}건")
    except Exception as e:
        logger.error(f"신뢰도 급변 알림 실패: {e}")


def register_jobs(sched: AsyncIOScheduler = scheduler) -> AsyncIOScheduler:
    sched.add_job(run_all_crawlers,      "cron", hour=0,  minute=0,  id="crawlers",   replace_existing=True)
    sched.add_job(run_dday_and_notify,   "cron", hour=0,  minute=5,  id="dday",       replace_existing=True)
    sched.add_job(collect_kmooc_lectures,"cron", hour=0,  minute=30, id="kmooc",      replace_existing=True)
    sched.add_job(collect_qnet_exams,    "cron", hour=1,  minute=0,  id="qnet",       replace_existing=True)
    sched.add_job(collect_all_reviews,   "cron", hour=2,  minute=0,  id="reviews",    replace_existing=True)
    sched.add_job(run_trust_score_check, "cron", day_of_week="mon", hour=9, minute=0,
                  id="trust_alert", replace_existing=True)
    return sched


def setup_scheduler() -> AsyncIOScheduler:
    """작업 등록 후 스케줄러 시작 (main.py 등 앱 기동 시 호출)."""
    register_jobs()
    scheduler.start()
    logger.info(f"스케줄러 시작 — 등록 작업 {len(scheduler.get_jobs())}개")
    return scheduler
