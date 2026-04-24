"""Captcha 恢复任务 — CaptchaRecoveryTask。

检测账号的 Captcha 阻断标记是否已清除（商家人工处理后）。
清除后恢复账号自动化操作。
"""

from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="worker.tasks.captcha_recovery_task.check_captcha_recovery",
)
async def check_captcha_recovery(self, account_id: str | None = None) -> dict:
    """检查并恢复已解除 Captcha 阻断的账号。

    由 Celery Beat 每 5 分钟触发一次。
    检测 Redis captcha_flag 是否已清除，恢复对应账号的自动化。

    Args:
        account_id: 可选，指定账号 ID。不指定则检查所有被阻断账号。

    Returns:
        检查结果统计。
    """
    # TODO: 实现 Captcha 恢复逻辑
    #
    # 1. 若 account_id 指定，只检查该账号：
    #    - 检查 Redis rpa:captcha_flag:{account_id} 是否仍存在
    #    - 若不存在，说明已清除，调用 clear_captcha_flag(account_id)
    #      并记录恢复日志，发送恢复通知
    # 2. 若未指定，遍历所有 captcha_flag 记录
    #    - 通过 SCAN 查找所有 rpa:captcha_flag:* key
    #    - 对每个 key 检查对应账号
    #
    # 注意：Captcha 恢复依赖商家人工处理，无自动破解方案

    return {
        "account_id": account_id,
        "recovered_accounts": 0,
        "still_blocked": 0,
        "status": "ok",
    }


@app.task(
    bind=True,
    max_retries=1,
    name="worker.tasks.captcha_recovery_task.manual_clear_captcha",
)
async def manual_clear_captcha(self, account_id: str) -> dict:
    """手动清除 Captcha 阻断标记（供商家操作后调用）。

    Args:
        account_id: 账号 ID。

    Returns:
        操作结果。
    """
    # TODO: 调用 clear_captcha_flag
    # from app.services.interaction_service import clear_captcha_flag
    # await clear_captcha_flag(account_id)
    return {
        "account_id": account_id,
        "status": "ok",
    }
