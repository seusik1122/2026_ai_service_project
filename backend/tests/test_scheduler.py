"""cron_jobs 스케줄러 등록 검증.

스케줄러를 실제로 start() 하지 않고 작업이 올바르게 등록되는지만 확인한다.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler.cron_jobs import register_jobs


def test_register_jobs_registers_expected_jobs():
    sched = AsyncIOScheduler()
    register_jobs(sched)

    jobs = {j.id: j for j in sched.get_jobs()}
    assert set(jobs) == {"crawlers", "dday", "kmooc", "qnet", "reviews"}


def test_register_jobs_cron_schedule():
    sched = AsyncIOScheduler()
    register_jobs(sched)
    jobs = {j.id: j for j in sched.get_jobs()}

    # 크롤링은 매일 자정, D-day는 00:05, 후기는 02:00
    assert "hour='0'" in str(jobs["crawlers"].trigger) and "minute='0'" in str(jobs["crawlers"].trigger)
    assert "minute='5'" in str(jobs["dday"].trigger)
    assert "hour='2'" in str(jobs["reviews"].trigger)
