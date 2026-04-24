"""Captcha 恢复任务 — CaptchaRecoveryTask。

Celery Beat 每 5 分钟触发。
检测账号的 Captcha 阻断标记是否已清除（商家人工处理后），清除后恢复自动化。
"""

from __future__ import annotations

import asyncio
import logging

from app.core.rate_limiter import get_redis
from app.core.notifications import send_alert
from app.services import interaction_service as svc
from worker.celery_app import app

logger = logging.getLogger(__name__)

CAPTCHA_FLAG_PREFIX = "rpa:captcha_flag:"


def check_captcha_recovery(self, account_id: str | None = None) -> dict:
    """检查并恢复已解除 Captcha 阻断的账号。

    由 Celery Beat 每 5 分钟触发一次。
    检测 Redis captcha_flag 是否已清除（由商家人工处理后删除 key），恢复对应账号的自动化。

    Args:
        account_id: 可选，指定账号 ID。不指定则遍历所有 captcha_flag 记录。

    Returns:
        检查结果统计。
    """
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _check_captcha_recovery(account_id))
        return result
    except Exception as exc:
        logger.exception("check_captcha_recovery failed, retrying...")
        raise self.retry(exc=exc)


async def _check_captcha_recovery(account_id: str | None) -> dict:
    """遍历 Redis 检查账号 Captcha 阻断恢复状态。"""
    redis = await get_redis()
    recovered = 0
    still_blocked = 0

    if account_id:
        account_ids = [account_id]
    else:
        pattern = f"{CAPTCHA_FLAG_PREFIX}*"
        keys = await redis.keys(pattern)
        account_ids = [k.replace(CAPTCHA_FLAG_PREFIX, "") for k in keys]

    for acct_id in account_ids:
        flag_key = f"{CAPTCHA_FLAG_PREFIX}{acct_id}"
        exists = await redis.exists(flag_key)

        if not exists:
            # key 已被删除（商家人工处理完成）
            await svc.clear_captcha_flag(acct_id)
            logger.info(f"Captcha recovered for account {acct_id}")
            recovered += 1

            # 发送恢复通知
            from app.models.account import Account
            from sqlalchemy import select
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                stmt = select(Account.merchant_id).where(Account.id == acct_id)
                result = await db.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    await send_alert(
                        merchant_id=str(row),
                        alert_type="captcha_recovered",
                        severity="info",
                        message=f"账号 {acct_id} 验证码已解除，自动化已恢复",
                    )
        else:
            still_blocked += 1

    return {
        "account_id": account_id,
        "recovered_accounts": recovered,
        "still_blocked": still_blocked,
        "status": "ok",
    }


def manual_clear_captcha(self, account_id: str) -> dict:
    """手动清除 Captcha 阻断标记（供商家操作后调用）。

    Args:
        account_id: 账号 ID。

    Returns:
        操作结果。
    """
    try:
        asyncio.get_event_loop().run_until_complete(
            _manual_clear_captcha(account_id))
        return {"account_id": account_id, "status": "ok"}
    except Exception as exc:
        logger.exception("manual_clear_captcha failed")
        return {"account_id": account_id, "status": "error", "error": str(exc)}


async def _manual_clear_captcha(account_id: str) -> None:
    """清除账号 Captcha 阻断标记并记录日志。"""
    await svc.clear_captcha_flag(account_id)
    logger.info(f"Captcha manually cleared for account {account_id}")


check_captcha_recovery_task = app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="worker.tasks.captcha_recovery_task.check_captcha_recovery",
)(check_captcha_recovery)

manual_clear_captcha_task = app.task(
    bind=True,
    max_retries=1,
    name="worker.tasks.captcha_recovery_task.manual_clear_captcha",
)(manual_clear_captcha)
