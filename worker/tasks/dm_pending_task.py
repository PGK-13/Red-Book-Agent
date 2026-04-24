"""待发送消息处理任务 — DMPendingTask。

处理 Redis session:pending:{conversation_id} 队列中的待发送消息。
连接恢复后 30 秒内补发回复。
"""

from __future__ import annotations

import json
import logging

from app.core.rate_limiter import get_redis
from worker.celery_app import app

logger = logging.getLogger(__name__)

PENDING_QUEUE_PREFIX = "session:pending:"


@app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    name="worker.tasks.dm_pending_task.process_pending_messages",
)
async def process_pending_messages(self, conversation_id: str | None = None) -> dict:
    """处理待发送消息队列。

    由 Celery Beat 每 10 秒触发一次。
    连接恢复后 30 秒内尝试补发 pending 队列中的消息。

    Args:
        conversation_id: 可选，指定会话 ID。不指定则处理所有 pending 会话。

    Returns:
        处理结果统计。
    """
    redis = await get_redis()
    processed = 0
    failed = 0
    skipped = 0

    # 确定要处理的会话列表
    if conversation_id:
        conversation_ids = [conversation_id]
    else:
        # 扫描所有 pending 会话
        pattern = f"{PENDING_QUEUE_PREFIX}*"
        keys = await redis.keys(pattern)
        conversation_ids = [k.replace(PENDING_QUEUE_PREFIX, "") for k in keys]

    for conv_id in conversation_ids:
        queue_key = f"{PENDING_QUEUE_PREFIX}{conv_id}"

        try:
            # 逐条处理 pending 消息
            while True:
                # 从队列左侧取出一条
                item_json = await redis.lpop(queue_key)
                if not item_json:
                    break

                try:
                    item = json.loads(item_json)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in pending queue: {item_json}")
                    skipped += 1
                    continue

                # 检查是否超时（30 秒内）
                import time
                from datetime import datetime, timezone

                timestamp = item.get("timestamp", "")
                if timestamp:
                    try:
                        item_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        elapsed = (datetime.now(timezone.utc) - item_time).total_seconds()
                        if elapsed > 30:
                            # 超过 30 秒，放弃并跳到下一条
                            logger.debug(f"Pending message timeout, skipping: {conv_id}")
                            skipped += 1
                            continue
                    except Exception:
                        pass

                # 尝试重新发送
                generated_reply = item.get("generated_reply")
                if generated_reply:
                    # TODO: 调用 send_dm_via_rpa
                    # success = await send_dm_via_rpa(...)
                    # if not success:
                    #     # 重新放回队列，等待下次重试
                    #     await redis.rpush(queue_key, item_json)
                    pass

                processed += 1

        except Exception as e:
            logger.error(f"Failed to process pending queue for {conv_id}: {e}")
            failed += 1

    return {
        "conversation_ids_processed": len(conversation_ids),
        "processed": processed,
        "failed": failed,
        "skipped": skipped,
        "status": "ok",
    }
