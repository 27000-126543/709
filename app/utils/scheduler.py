import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.services import (
    ApprovalService,
    ReportService,
    ConsumableService,
    FollowUpService,
)

logger = logging.getLogger(__name__)


class SchedulerManager:
    _instance: Optional["SchedulerManager"] = None

    def __new__(cls) -> "SchedulerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._initialized = True

    async def _approval_timeout_task(self) -> None:
        try:
            import app.database as db
            async with db.async_session() as session:
                service = ApprovalService(session)
                result = await service.check_and_process_timeouts()
                logger.info(f"审批超时检查完成，处理了 {len(result)} 条超时审批")
                await session.commit()
        except Exception as e:
            logger.error(f"审批超时检查任务出错: {e}", exc_info=True)

    async def _daily_report_task(self) -> None:
        try:
            import app.database as db
            async with db.async_session() as session:
                service = ReportService(session)
                result = await service.generate_daily_report()
                logger.info(f"每日报表生成完成: {result}")
                await session.commit()
        except Exception as e:
            logger.error(f"每日报表生成任务出错: {e}", exc_info=True)

    async def _consumable_low_stock_task(self) -> None:
        try:
            import app.database as db
            async with db.async_session() as session:
                service = ConsumableService(session)
                alerts = await service.check_all_safety_stocks()
                logger.info(f"耗材安全水位检查完成，发现 {len(alerts)} 条低库存告警")
                await session.commit()
        except Exception as e:
            logger.error(f"耗材安全水位检查任务出错: {e}", exc_info=True)

    async def _followup_due_task(self) -> None:
        try:
            import app.database as db
            async with db.async_session() as session:
                service = FollowUpService(session)
                overdue = await service.list_recipients_needing_followup()
                logger.info(f"随访到期检查完成，发现 {len(overdue)} 条需随访提醒")
                await session.commit()
        except Exception as e:
            logger.error(f"随访到期检查任务出错: {e}", exc_info=True)

    def register_all_tasks(self) -> None:
        self.scheduler.add_job(
            self._approval_timeout_task,
            trigger=IntervalTrigger(minutes=15),
            id="approval_timeout_check",
            name="审批超时自动转交检查",
            replace_existing=True,
        )
        logger.info("已注册定时任务: approval_timeout_check (每15分钟)")

        self.scheduler.add_job(
            self._daily_report_task,
            trigger=CronTrigger(hour=0, minute=0),
            id="daily_report_generation",
            name="每日凌晨报表生成",
            replace_existing=True,
        )
        logger.info("已注册定时任务: daily_report_generation (每天凌晨0点)")

        self.scheduler.add_job(
            self._consumable_low_stock_task,
            trigger=IntervalTrigger(hours=1),
            id="consumable_low_stock_check",
            name="耗材安全水位检查",
            replace_existing=True,
        )
        logger.info("已注册定时任务: consumable_low_stock_check (每小时)")

        self.scheduler.add_job(
            self._followup_due_task,
            trigger=CronTrigger(hour=8, minute=0),
            id="followup_due_check",
            name="每日随访到期检查",
            replace_existing=True,
        )
        logger.info("已注册定时任务: followup_due_check (每天早8点)")

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler 调度器已启动")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler 调度器已关闭")
