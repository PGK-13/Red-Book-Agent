"""私信探测任务 — DMProbeTask。

Celery Beat 定时触发（每 5 秒）。
遍历所有活跃账号，检测新私信并触发自动回复。
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.models.account import Account
from app.services import interaction_service as svc
from worker.celery_app import app

logger = logging.getLogger(__name__)


def poll_dm_messages(self, account_id: str | None = None) -> dict:
    """轮询私信消息。

    由 Celery Beat 每 5 秒触发一次。
    遍历指定账号（或所有活跃账号），检测新私信并触发自动回复。

    Args:
        account_id: 可选，指定账号 ID。

    Returns:
        轮询结果统计。
    """
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _poll_dm_messages(account_id)
        )
        return result
    except Exception as exc:
        logger.exception("poll_dm_messages failed, retrying...")
        raise self.retry(exc=exc)


async def _poll_dm_messages(account_id: str | None) -> dict:
    """遍历账号执行私信轮询。"""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        if account_id:
            account_ids = [account_id]
        else:
            # 遍历所有活跃账号
            stmt = select(Account.id).where(Account.status == "active")
            result = await db.execute(stmt)
            account_ids = [str(r) for r in result.scalars().all()]

        total_messages = 0
        total_replies = 0
        errors = []

        for acct_id in account_ids:
            try:
                if await svc.is_captcha_blocked(acct_id):
                    continue

                acct_stmt = select(Account.status).where(Account.id == acct_id)
                acct_result = await db.execute(acct_stmt)
                status = acct_result.scalar_one_or_none()
                if status in {"auth_expired", "banned", "suspended"}:
                    continue

                result = await svc.poll_dm_messages(account_id=acct_id, db=db)
                total_messages += result.get("new_messages", 0)
                total_replies += result.get("replies_sent", 0)

            except Exception as e:
                logger.error(f"Failed to poll DM for account {acct_id}: {e}")
                errors.append({"account_id": acct_id, "error": str(e)})

        await db.commit()
        return {
            "account_id": account_id,
            "new_messages": total_messages,
            "replies_sent": total_replies,
            "errors": errors,
            "status": "ok",
        }


def poll_single_conversation(self, conversation_id: str, account_id: str) -> dict:
    """轮询单个会话的新消息。

    供手动触发或单独监控使用。

    Args:
        conversation_id: 会话 ID。
        account_id: 账号 ID。

    Returns:
        轮询结果。
    """
    # 单会话轮询暂不单独实现，由 poll_dm_messages 统一处理
    return {
        "conversation_id": conversation_id,
        "account_id": account_id,
        "new_messages": 0,
        "status": "ok",
        "note": "Use poll_dm_messages to poll all conversations for an account",
    }


poll_dm_messages_task = app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="worker.tasks.dm_probe_task.poll_dm_messages",
)(poll_dm_messages)

poll_single_conversation_task = app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="worker.tasks.dm_probe_task.poll_single_conversation",
)(poll_single_conversation)
