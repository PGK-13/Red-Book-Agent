"""笔记轮询调度器 — NotePollingScheduler。

基于令牌桶算法控制每账号每批次笔记处理量，注入随机抖动以避免固定模式检测。
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

from app.core.rate_limiter import get_redis

logger = logging.getLogger(__name__)


# ── Redis Key ────────────────────────────────────────────────────────────────

_TOKEN_BUCKET_KEY = "rpa:token_bucket:{account_id}"
_LAST_PROBE_KEY = "rpa:last_probe:{account_id}"


# ── Scheduler State ─────────────────────────────────────────────────────────


@dataclass
class TokenBucket:
    """令牌桶状态。"""

    tokens: float  # 当前令牌数
    last_refill_at: float  # 上次补充时间（Unix timestamp）
    capacity: float  # 桶容量
    refill_rate: float  # 每秒补充令牌数


# ── Scheduler ───────────────────────────────────────────────────────────────


class NotePollingScheduler:
    """笔记轮询调度器。

    令牌桶算法 + 随机抖动，控制每账号每批次笔记处理量。
    避免固定频率轮询被平台检测。

    防检测设计：
    - 令牌桶限制处理速率
    - 每批笔记处理之间注入 3~15 秒随机延迟
    - 批次开始前 5~25 秒随机等待
    - 基础间隔 ±50% 随机抖动

    使用方式：
    ```python
    scheduler = NotePollingScheduler()
    should_run, delay = await scheduler.should_probe_now(account_id="xxx")
    if should_run:
        await scheduler.run_batch(account_id, notes, check_fn)
    ```
    """

    def __init__(
        self,
        capacity: float = 10.0,
        refill_rate: float = 1.0,
        min_probe_interval: float = 60.0,
        max_jitter: float = 0.5,
    ) -> None:
        """初始化调度器。

        Args:
            capacity: 令牌桶容量（每次最大处理批次数）。
            refill_rate: 每秒补充令牌数。
            min_probe_interval: 最小探测间隔（秒）。
            max_jitter: 抖动比例上限（±50%）。
        """
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._min_probe_interval = min_probe_interval
        self._max_jitter = max_jitter

    async def _get_bucket(self, account_id: str) -> TokenBucket:
        """从 Redis 获取（或初始化）令牌桶状态。"""
        redis = await get_redis()
        bucket_key = _TOKEN_BUCKET_KEY.format(account_id=account_id)

        data = await redis.hgetall(bucket_key)

        if data:
            return TokenBucket(
                tokens=float(data.get("tokens", self._capacity)),
                last_refill_at=float(data.get("last_refill_at", time.time())),
                capacity=self._capacity,
                refill_rate=self._refill_rate,
            )
        else:
            return TokenBucket(
                tokens=self._capacity,
                last_refill_at=time.time(),
                capacity=self._capacity,
                refill_rate=self._refill_rate,
            )

    async def _save_bucket(self, account_id: str, bucket: TokenBucket) -> None:
        """保存令牌桶状态到 Redis。"""
        redis = await get_redis()
        bucket_key = _TOKEN_BUCKET_KEY.format(account_id=account_id)

        await redis.hset(bucket_key, mapping={
            "tokens": str(bucket.tokens),
            "last_refill_at": str(bucket.last_refill_at),
        })

    def _refill(self, bucket: TokenBucket) -> None:
        """补充令牌。"""
        now = time.time()
        elapsed = now - bucket.last_refill_at
        bucket.tokens = min(
            bucket.capacity,
            bucket.tokens + elapsed * bucket.refill_rate,
        )
        bucket.last_refill_at = now

    def get_jitter_delay(self, base_delay: float) -> float:
        """返回带随机抖动的延迟（基础延迟 ±50%）。

        Args:
            base_delay: 基础延迟（秒）。

        Returns:
            带随机抖动的延迟（秒）。
        """
        jitter_range = base_delay * self._max_jitter
        return base_delay + random.uniform(-jitter_range, jitter_range)

    def get_batch_start_delay(self) -> float:
        """批次开始前随机等待 5~25 秒。

        Returns:
            随机等待秒数。
        """
        return random.uniform(5.0, 25.0)

    def get_inter_batch_delay(self) -> float:
        """批次之间随机等待 3~15 秒。

        Returns:
            随机等待秒数。
        """
        return random.uniform(3.0, 15.0)

    async def should_probe_now(self, account_id: str) -> tuple[bool, float]:
        """判断当前是否应该触发探测。

        Args:
            account_id: 账号 ID。

        Returns:
            (是否应探测, 建议等待时间)。
        """
        redis = await get_redis()
        last_probe_key = _LAST_PROBE_KEY.format(account_id=account_id)

        last_probe = await redis.get(last_probe_key)
        now = time.time()

        if last_probe:
            elapsed = now - float(last_probe)
            jittered_interval = self.get_jitter_delay(self._min_probe_interval)

            if elapsed < jittered_interval:
                return False, jittered_interval - elapsed

        return True, 0.0

    async def acquire(self, account_id: str, tokens_needed: float = 1.0) -> bool:
        """尝试获取令牌。

        Args:
            account_id: 账号 ID。
            tokens_needed: 需要消耗的令牌数。

        Returns:
            True 表示获取成功，False 表示令牌不足。
        """
        bucket = await self._get_bucket(account_id)
        self._refill(bucket)

        if bucket.tokens >= tokens_needed:
            bucket.tokens -= tokens_needed
            await self._save_bucket(account_id, bucket)
            return True
        else:
            await self._save_bucket(account_id, bucket)
            return False

    async def mark_probe_done(self, account_id: str) -> None:
        """标记探测完成，更新最后探测时间。"""
        redis = await get_redis()
        last_probe_key = _LAST_PROBE_KEY.format(account_id=account_id)
        await redis.set(last_probe_key, str(time.time()))

    async def run_batch(
        self,
        account_id: str,
        notes: list,
        process_fn,
        batch_size: int = 3,
    ) -> int:
        """执行一批笔记的探测。

        Args:
            account_id: 账号 ID。
            notes: 笔记列表。
            process_fn: 处理单篇笔记的异步函数，签名为 `async def process(note) -> None`。
            batch_size: 每批处理数量。

        Returns:
            实际处理数量。
        """
        # 检查是否应该探测
        should_run, wait_time = await self.should_probe_now(account_id)
        if not should_run:
            logger.debug(f"Probe skipped for {account_id}, wait {wait_time:.1f}s")
            return 0

        # 批次开始前随机等待
        await asyncio.sleep(self.get_batch_start_delay())

        processed = 0

        # 分批处理
        for i in range(0, len(notes), batch_size):
            batch = notes[i : i + batch_size]

            # 尝试获取令牌
            acquired = await self.acquire(account_id, tokens_needed=len(batch))
            if not acquired:
                logger.debug(f"Token bucket empty for {account_id}, stopping batch")
                break

            for note in batch:
                try:
                    await process_fn(note)
                    processed += 1

                    # 每篇笔记处理后注入随机延迟
                    await asyncio.sleep(self.get_inter_batch_delay())

                except Exception as e:
                    logger.error(f"Failed to process note {note}: {e}")
                    continue

        # 标记探测完成
        await self.mark_probe_done(account_id)

        return processed
