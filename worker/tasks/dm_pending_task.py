"""待发送消息处理任务 — DMPendingTask。

Celery Beat 每 10 秒触发。
处理 Redis session:pending:{conversation_id} 队列中的待发送消息，30 秒内补发。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.rate_limiter import get_redis
from app.models.interaction import Conversation
from app.services import interaction_service as svc
from worker.celery_app import app

logger = logging.getLogger(__name__)

PENDING_QUEUE_PREFIX = "session:pending:"
MAX_RETRY_SECONDS = 30


def process_pending_messages(self, conversation_id: str | None = None) -> dict:
    """处理待发送消息队列。

    由 Celery Beat 每 10 秒触发一次。
    遍历所有 pending 队列，30 秒内的消息尝试补发。

    Args:
        conversation_id: 可选，指定会话 ID。

    Returns:
        处理结果统计。
    """
    try:
        result = asyncio.get_event_loop().run_until_complete(
            _process_pending_messages(conversation_id))
        return result
    except Exception as exc:
        logger.exception("process_pending_messages failed, retrying...")
        raise self.retry(exc=exc)


async def _process_pending_messages(conversation_id: str | None) -> dict:
    """遍历 pending 队列，尝试补发未发送的消息。"""
    redis = await get_redis()
    processed = 0
    failed = 0
    skipped = 0

    if conversation_id:
        conversation_ids = [conversation_id]
    else:
        pattern = f"{PENDING_QUEUE_PREFIX}*"
        keys = await redis.keys(pattern)
        conversation_ids = [k.replace(PENDING_QUEUE_PREFIX, "") for k in keys]

    for conv_id in conversation_ids:
        queue_key = f"{PENDING_QUEUE_PREFIX}{conv_id}"

        try:
            while True:
                item_json = await redis.lpop(queue_key)
                if not item_json:
                    break

                try:
                    item = json.loads(item_json)
                except json.JSONDecodeError:
                    skipped += 1
                    continue

                timestamp = item.get("timestamp", "")
                if timestamp:
                    try:
                        item_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        elapsed = (datetime.now(timezone.utc) - item_time).total_seconds()
                        if elapsed > MAX_RETRY_SECONDS:
                            skipped += 1
                            continue
                    except Exception:
                        pass

                generated_reply = item.get("generated_reply")
                if not generated_reply:
                    skipped += 1
                    continue

                # 从数据库获取会话信息
                from app.db.session import AsyncSessionLocal

                async with AsyncSessionLocal() as db:
                    stmt = select(Conversation).where(Conversation.id == conv_id)
                    result = await db.execute(stmt)
                    conversation = result.scalar_one_or_none()

                    if not conversation:
                        logger.warning(f"Conversation {conv_id} not found")
                        skipped += 1
                        continue

                    # 检查 Captcha 和账号状态
                    if await svc.is_captcha_blocked(conversation.account_id):
                        await redis.rpush(queue_key, item_json)
                        failed += 1
                        continue

                    success, error = await svc.send_dm_via_rpa(
                        merchant_id=conversation.merchant_id,
                        account_id=conversation.account_id,
                        xhs_user_id=conversation.xhs_user_id,
                        content=generated_reply,
                        db=db,
                    )

                    if success:
                        await db.commit()
                        processed += 1
                        logger.info(f"Pending DM sent for conversation {conv_id}")
                    else:
                        # 失败重新放回队列
                        await redis.rpush(queue_key, item_json)
                        failed += 1
                        logger.warning(f"Failed to resend DM: {error}")

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


process_pending_messages_task = app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    name="worker.tasks.dm_pending_task.process_pending_messages",
)(process_pending_messages)
