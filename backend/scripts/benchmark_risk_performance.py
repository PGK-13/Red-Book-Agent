"""Benchmark Module E risk scan performance inside a Docker-backed environment."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.models.account import Account
from app.models.risk import RiskKeyword
from app.services import risk_service


class _BenchmarkRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    async def incr(self, key: str) -> int:
        next_value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(next_value)
        return next_value

    async def incrby(self, key: str, amount: int) -> int:
        next_value = int(self.values.get(key, "0")) + amount
        self.values[key] = str(next_value)
        return next_value

    async def expire(self, key: str, seconds: int) -> bool:
        _ = (key, seconds)
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        _ = seconds
        self.values[key] = value
        return True

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self.lists.get(key, [])
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    async def lpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        items = self.lists.get(key, [])
        self.lists[key] = items[start : end + 1]
        return True

    async def delete(self, key: str) -> int:
        deleted = 0
        if key in self.values:
            del self.values[key]
            deleted += 1
        if key in self.lists:
            del self.lists[key]
            deleted += 1
        return deleted

    async def rpush(self, key: str, *values: str) -> int:
        self.lists.setdefault(key, []).extend(values)
        return len(self.lists[key])


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


async def _measure_scan_sensitive_keywords(session, merchant_id: str, dataset: list[dict]) -> list[dict]:
    results: list[dict] = []
    for item in dataset:
        durations: list[float] = []
        for _ in range(item["iterations"]):
            started_at = perf_counter()
            hits = await risk_service.scan_sensitive_keywords(
                content=item["content"],
                merchant_id=merchant_id,
                db=session,
            )
            durations.append((perf_counter() - started_at) * 1000)

        results.append(
            {
                "name": item["name"],
                "mode": item["mode"],
                "content_length": len(item["content"]),
                "iterations": item["iterations"],
                "hit_count": len(hits),
                "mean_ms": round(statistics.fmean(durations), 3),
                "p50_ms": round(_percentile(durations, 0.50), 3),
                "p95_ms": round(_percentile(durations, 0.95), 3),
                "max_ms": round(max(durations), 3),
            }
        )
    return results


async def _measure_scan_output(
    session,
    merchant_id: str,
    account_id: str,
    dataset: list[dict],
    fake_redis: _BenchmarkRedis,
) -> list[dict]:
    results: list[dict] = []
    for item in dataset:
        durations: list[float] = []
        last_decision = "unknown"
        for _ in range(item["iterations"]):
            fake_redis.values.clear()
            fake_redis.lists.clear()
            started_at = perf_counter()
            decision = await risk_service.scan_output(
                merchant_id=merchant_id,
                account_id=account_id,
                scene=item["scene"],
                content=item["content"],
                db=session,
            )
            durations.append((perf_counter() - started_at) * 1000)
            last_decision = decision.decision

        results.append(
            {
                "name": item["name"],
                "scene": item["scene"],
                "content_length": len(item["content"]),
                "iterations": item["iterations"],
                "decision": last_decision,
                "mean_ms": round(statistics.fmean(durations), 3),
                "p50_ms": round(_percentile(durations, 0.50), 3),
                "p95_ms": round(_percentile(durations, 0.95), 3),
                "max_ms": round(max(durations), 3),
            }
        )
    return results


def _build_sensitive_dataset() -> list[dict]:
    long_clean_text = " ".join(["safe content for benchmark"] * 80)
    long_fuzzy_text = " ".join(["bramd mention in reply copy"] * 80)
    return [
        {
            "name": "exact_short_clean",
            "mode": "exact",
            "content": "hello there this reply is safe",
            "iterations": 30,
        },
        {
            "name": "exact_short_multi_hit",
            "mode": "exact",
            "content": "forbidden promo offer forbidden promo",
            "iterations": 30,
        },
        {
            "name": "exact_long_clean",
            "mode": "exact",
            "content": long_clean_text,
            "iterations": 30,
        },
        {
            "name": "fuzzy_long_multi_hit",
            "mode": "fuzzy",
            "content": long_fuzzy_text,
            "iterations": 20,
        },
    ]


def _build_output_dataset() -> list[dict]:
    long_safe_publish = " ".join(["safe publish body"] * 100)
    return [
        {
            "name": "output_pass_note_publish",
            "scene": "note_publish",
            "content": long_safe_publish,
            "iterations": 20,
        },
        {
            "name": "output_block_dm_send",
            "scene": "dm_send",
            "content": "forbidden outbound message for benchmark",
            "iterations": 20,
        },
        {
            "name": "output_rewrite_comment_reply",
            "scene": "comment_reply",
            "content": "brandx comparison is a bramd mention benchmark",
            "iterations": 20,
        },
    ]


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    fake_redis = _BenchmarkRedis()
    original_get_redis = risk_service.get_redis
    risk_service.get_redis = lambda: fake_redis

    merchant_id = str(uuid4())
    account_id = str(uuid4())
    summary: dict[str, object]

    try:
        async with session_factory() as session:
            account = Account(
                id=account_id,
                merchant_id=merchant_id,
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="risk-benchmark-account",
                access_type="browser",
                status="active",
            )
            session.add(account)

            keywords = [
                RiskKeyword(
                    merchant_id=None,
                    keyword="forbidden",
                    category="platform_banned",
                    replacement="allowed",
                    match_mode="exact",
                    severity="block",
                    is_active=True,
                ),
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword="promo",
                    category="custom",
                    replacement="intro",
                    match_mode="exact",
                    severity="warn",
                    is_active=True,
                ),
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword="brandx",
                    category="competitor",
                    replacement="our brand",
                    match_mode="exact",
                    severity="warn",
                    is_active=True,
                ),
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword="brand",
                    category="custom",
                    replacement=None,
                    match_mode="fuzzy",
                    severity="warn",
                    is_active=True,
                ),
            ]

            for index in range(40):
                keywords.append(
                    RiskKeyword(
                        merchant_id=merchant_id,
                        keyword=f"safe_keyword_{index}",
                        category="custom",
                        replacement=f"safe_replacement_{index}",
                        match_mode="exact",
                        severity="warn",
                        is_active=True,
                    )
                )

            session.add_all(keywords)
            await session.flush()

            sensitive_dataset = _build_sensitive_dataset()
            output_dataset = _build_output_dataset()

            sensitive_results = await _measure_scan_sensitive_keywords(
                session=session,
                merchant_id=merchant_id,
                dataset=sensitive_dataset,
            )
            output_results = await _measure_scan_output(
                session=session,
                merchant_id=merchant_id,
                account_id=account_id,
                dataset=output_dataset,
                fake_redis=fake_redis,
            )
            await session.rollback()

        fuzzy_results = [item for item in sensitive_results if item["mode"] == "fuzzy"]
        exact_results = [item for item in sensitive_results if item["mode"] == "exact"]
        summary = {
            "environment": {
                "database_url": settings.database_url,
                "keyword_count": 44,
                "account_count": 1,
                "iterations": {
                    "scan_sensitive_keywords": sum(item["iterations"] for item in sensitive_dataset),
                    "scan_output": sum(item["iterations"] for item in output_dataset),
                },
            },
            "scan_sensitive_keywords": sensitive_results,
            "scan_output": output_results,
            "analysis": {
                "exact_p95_ms": round(max(item["p95_ms"] for item in exact_results), 3),
                "fuzzy_p95_ms": round(max(item["p95_ms"] for item in fuzzy_results), 3),
                "fuzzy_over_exact_ratio": round(
                    max(item["p95_ms"] for item in fuzzy_results)
                    / max(item["p95_ms"] for item in exact_results),
                    3,
                ),
            },
        }
    finally:
        risk_service.get_redis = original_get_redis
        await engine.dispose()

    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
