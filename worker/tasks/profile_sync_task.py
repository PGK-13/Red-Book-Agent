"""账号画像同步 Celery 任务。

每 24 小时凌晨 3 点由 Celery Beat 触发，通过 Playwright 抓取小红书个人主页，
同步昵称、简介、标签、粉丝数等画像数据。
业务逻辑复用 AccountService，此处仅做异步入口和会话管理。
"""

from __future__ import annotations

import asyncio
import logging

from worker.celery_app import app

logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    name="worker.tasks.profile_sync_task.sync_all_profiles",
)
def sync_all_profiles(self) -> dict:
    """每 24h 同步账号画像（粉丝数、简介、标签等）。"""
    try:
        result = asyncio.get_event_loop().run_until_complete(_sync_all())
        return result
    except Exception as exc:
        logger.exception("profile_sync_task failed, retrying...")
        raise self.retry(exc=exc)


async def _sync_all() -> dict:
    """查询所有 active 账号，逐个调用 AccountService.sync_profile。"""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.account import Account
    from app.services import account_service

    async with AsyncSessionLocal() as db:
        try:
            stmt = select(Account).where(Account.status == "active")
            result = await db.execute(stmt)
            accounts = result.scalars().all()

            synced = 0
            failed = 0
            for acct in accounts:
                try:
                    await account_service.sync_profile(acct.merchant_id, acct.id, db)
                    synced += 1
                except Exception:
                    logger.exception("Failed to sync profile for account %s", acct.id)
                    failed += 1

            await db.commit()
            logger.info(
                "Profile sync completed: %d synced, %d failed out of %d",
                synced,
                failed,
                len(accounts),
            )
            return {"total": len(accounts), "synced": synced, "failed": failed}
        except Exception:
            await db.rollback()
            raise
