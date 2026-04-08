import json

import redis.asyncio as aioredis

from app.config import settings

CONTEXT_WINDOW = 10  # 保留最近 10 轮对话


class ShortTermMemory:
    """Redis 短期记忆：存储会话最近 10 轮对话上下文。"""

    def __init__(self) -> None:
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def get_context(self, conversation_id: str) -> list[dict]:
        """获取会话上下文（最近 10 轮）。"""
        key = f"context:{conversation_id}"
        raw = await self._redis.lrange(key, -CONTEXT_WINDOW * 2, -1)
        return [json.loads(m) for m in raw]

    async def append_message(self, conversation_id: str, role: str, content: str) -> None:
        """追加消息到上下文，超出窗口自动截断。"""
        key = f"context:{conversation_id}"
        message = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        await self._redis.rpush(key, message)
        await self._redis.ltrim(key, -CONTEXT_WINDOW * 2, -1)
        await self._redis.expire(key, 86400)  # 24h TTL
