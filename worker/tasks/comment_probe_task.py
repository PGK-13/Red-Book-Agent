"""评论探测任务 — CommentProbeTask。

Celery Beat 定时触发（每 10 秒）。
遍历账号下的监测笔记，调用 NotePollingScheduler + InteractionService 执行增量评论检测。
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.models.account import Account
from app.models.interaction import MonitoredNote
from app.services import interaction_service as svc
from worker.celery_app import app

logger = logging.getLogger(__name__)


def probe_monitored_notes(self, account_id: str | None = None) -> dict:
    """探测所有监测笔记的新评论。

    由 Celery Beat 每 10 秒触发一次。
    通过 NotePollingScheduler 控制探测频率，对账号下所有激活笔记执行增量检测。

    Args:
        account_id: 可选，指定账号 ID。不指定则遍历所有有监测笔记的账号。

    Returns:
        探测结果统计：processed_notes, new_comments, triggered_dms。
    """
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _probe_monitored_notes(account_id)
        )
        return result
    except Exception as exc:
        logger.exception("probe_monitored_notes failed, retrying...")
        raise self.retry(exc=exc)


async def _probe_monitored_notes(account_id: str | None) -> dict:
    """遍历账号执行增量评论检测。"""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        if account_id:
            account_ids = [account_id]
        else:
            stmt = select(MonitoredNote.account_id).distinct()
            result = await db.execute(stmt)
            account_ids = [str(r) for r in result.scalars().all()]

        total_notes = 0
        total_comments = 0
        total_dms = 0
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

                result = await svc.check_monitored_notes(account_id=acct_id, db=db)
                total_notes += result.get("processed_notes", 0)
                total_comments += result.get("new_comments", 0)
                total_dms += result.get("triggered_dms", 0)

            except Exception as e:
                logger.error(f"Failed to probe account {acct_id}: {e}")
                errors.append({"account_id": acct_id, "error": str(e)})

        await db.commit()
        return {
            "account_id": account_id,
            "processed_notes": total_notes,
            "new_comments": total_comments,
            "triggered_dms": total_dms,
            "errors": errors,
            "status": "ok",
        }


def probe_single_note(self, note_id: str, account_id: str) -> dict:
    """探测单篇笔记的新评论。

    供手动触发或单独监控使用。

    Args:
        note_id: 笔记配置 ID（monitored_notes 表主键）。
        account_id: 账号 ID。

    Returns:
        探测结果。
    """
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _probe_single_note(note_id, account_id)
        )
        return result
    except Exception as exc:
        logger.exception("probe_single_note failed, retrying...")
        raise self.retry(exc=exc)


async def _probe_single_note(note_id: str, account_id: str) -> dict:
    """对指定笔记执行增量评论检测。"""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        stmt = select(MonitoredNote).where(MonitoredNote.id == note_id)
        result = await db.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            return {"note_id": note_id, "account_id": account_id, "new_comments": 0, "error": "Note not found"}

        if await svc.is_captcha_blocked(account_id):
            return {"note_id": note_id, "account_id": account_id, "new_comments": 0, "error": "Captcha blocked"}

        acct_stmt = select(Account.status).where(Account.id == account_id)
        acct_result = await db.execute(acct_stmt)
        status = acct_result.scalar_one_or_none()
        if status in {"auth_expired", "banned", "suspended"}:
            return {"note_id": note_id, "account_id": account_id, "new_comments": 0, "error": f"Account status: {status}"}

        result = await svc.process_single_note_comments(
            merchant_id=note.merchant_id,
            note_id=note_id,
            db=db,
        )
        await db.commit()

        return {
            "note_id": note_id,
            "account_id": account_id,
            "new_comments": result.get("new_comments", 0),
            "triggered_dms": result.get("triggered_dms", 0),
            "status": "ok",
        }


# Celery task 装饰器（bind=True 需单独应用）
probe_monitored_notes_task = app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="worker.tasks.comment_probe_task.probe_monitored_notes",
)(probe_monitored_notes)

probe_single_note_task = app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="worker.tasks.comment_probe_task.probe_single_note",
)(probe_single_note)
