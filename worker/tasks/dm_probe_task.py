"""私信探测任务 — DMProbeTask。

Celery Beat 定时触发（建议每 5~10 秒检查一次）。
遍历所有活跃账号，检查令牌桶，调用 InteractionService.poll_dm_messages()。
"""

from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="worker.tasks.dm_probe_task.poll_dm_messages",
)
async def poll_dm_messages(self, account_id: str | None = None) -> dict:
    """轮询私信消息。

    由 Celery Beat 每 5~10 秒触发一次。
    遍历指定账号（或所有活跃账号），检测新私信并触发自动回复。

    Args:
        account_id: 可选，指定账号 ID。

    Returns:
        轮询结果统计。
    """
    # TODO: 实现私信轮询逻辑
    #
    # 1. 若 account_id 指定，只处理该账号：
    #    - 检查账号状态（auth_expired/banned → 跳过）
    #    - 检查 captcha 阻断标志
    # 2. 若未指定，遍历所有活跃账号
    #
    # 3. 对每个账号：
    #    - 获取 Redis 已知的消息 ID 集合
    #    - 调用 playwright_dm_monitor.poll_dm_messages()
    #    - 对每条新消息：
    #      - 写入 messages 表（append_message）
    #      - 判断是否需要触发自动回复
    #      - 调用 CustomerServiceGraph.reply()
    #    - 更新 Redis 已知消息 ID 集合
    #
    # 4. 返回统计

    return {
        "account_id": account_id,
        "new_messages": 0,
        "replies_sent": 0,
        "status": "ok",
    }


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="worker.tasks.dm_probe_task.poll_single_conversation",
)
async def poll_single_conversation(
    self,
    conversation_id: str,
    account_id: str,
) -> dict:
    """轮询单个会话的新消息。

    供手动触发或单独监控使用。

    Args:
        conversation_id: 会话 ID。
        account_id: 账号 ID。

    Returns:
        轮询结果。
    """
    # TODO: 实现单会话轮询逻辑

    return {
        "conversation_id": conversation_id,
        "account_id": account_id,
        "new_messages": 0,
        "status": "ok",
    }
