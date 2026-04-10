"""账号状态探测 Celery 任务。

每 10 分钟由 Celery Beat 触发，探测所有活跃账号的 Cookie 过期和平台状态。
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
    name="worker.tasks.account_probe_task.probe_all_accounts",
)
def probe_all_accounts(self) -> dict:
    """每 10min 探测所有账号状态，检测 Cookie 过期、封号等异常。"""
    try:
        result = asyncio.get_event_loop().run_until_complete(_probe_all())
        return result
    except Exception as exc:
        logger.exception("account_probe_task failed, retrying...")
        raise self.retry(exc=exc)


async def _probe_all() -> dict:
    """创建数据库会话并调用 AccountService.probe_all_accounts。"""
    from app.db.session import AsyncSessionLocal
    from app.services import account_service

    async with AsyncSessionLocal() as db:
        try:
            results = await account_service.probe_all_accounts(db)
            await db.commit()
            logger.info(
                "Account probe completed: %d accounts checked", len(results)
            )
            return {"probed": len(results), "results": results}
        except Exception:
            await db.rollback()
            raise
