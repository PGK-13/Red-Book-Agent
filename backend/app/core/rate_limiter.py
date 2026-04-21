import redis.asyncio as aioredis
from app.config import settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def check_rate_limit(
    account_id: str,
    operation: str,
    limit: int,
    window_seconds: int = 3600,
) -> bool:
    """
    检查账号操作频率是否超限（滑动窗口）。

    Returns:
        True 表示未超限可继续，False 表示已超限需暂停。
    """
    redis = get_redis()
    key = f"rate_limit:{account_id}:{operation}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count <= limit
