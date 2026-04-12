from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.account import Account
from app.models.analytics import OperationLog
from app.models.content import ContentDraft
from app.models.risk import ReplyHistory, RiskKeyword
from app.services import content_service, interaction_service


def _make_auth_header(merchant_id: str) -> dict[str, str]:
    token = jwt.encode(
        {"sub": merchant_id},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = defaultdict(list)

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
        self.lists[key].insert(0, value)
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
        self.lists[key].extend(values)
        return len(self.lists[key])


@pytest.mark.asyncio
async def test_phase2_content_smoke_rewrite_rescan_and_event_contract(
    db: AsyncSession,
    client: AsyncClient,
) -> None:
    merchant_id = str(uuid4())
    account = Account(
        id=str(uuid4()),
        merchant_id=merchant_id,
        xhs_user_id=f"xhs_{uuid4().hex[:8]}",
        nickname="phase2-content-smoke",
        access_type="browser",
        status="active",
    )
    draft = ContentDraft(
        account_id=account.id,
        title="promo title",
        body="promo body copy",
        alt_titles=["promo alt"],
        hashtags=["promo-tag"],
        risk_status="pending",
        status="draft",
    )
    db.add_all([account, draft])
    db.add(
        RiskKeyword(
            merchant_id=merchant_id,
            keyword="promo",
            category="custom",
            replacement="intro",
            match_mode="exact",
            severity="warn",
            is_active=True,
        )
    )
    await db.flush()

    fake_redis = _FakeRedis()
    with patch("app.services.risk_service.get_redis", return_value=fake_redis):
        result = await content_service.review_draft_outbound_risk(
            merchant_id=merchant_id,
            draft_id=draft.id,
            db=db,
        )
        await db.commit()

    assert result.decision.decision == "passed"
    assert result.attempts_used == 1
    assert draft.risk_status == "passed"
    assert "intro" in draft.title

    logs = (
        await db.execute(
            select(OperationLog)
            .where(OperationLog.account_id == account.id)
            .order_by(OperationLog.created_at.asc())
        )
    ).scalars().all()
    assert len(logs) == 2
    assert logs[0].detail["detail_schema"] == "module_e_risk_event.v1"
    assert logs[0].detail["merchant_id"] == merchant_id
    assert logs[0].detail["context"]["reason"] == "sensitive_keywords"
    assert logs[1].detail["risk_decision"] == "passed"

    resp = await client.get(
        f"/api/v1/risk/accounts/{account.id}/events?operation_type=note_publish",
        headers=_make_auth_header(merchant_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"][0]["merchant_id"] == merchant_id
    assert body["data"][0]["module"] == "E"
    assert body["data"][0]["detail_schema"] == "module_e_risk_event.v1"


@pytest.mark.asyncio
async def test_phase2_interaction_smoke_blocked_and_passed_paths(
    db: AsyncSession,
) -> None:
    merchant_id = str(uuid4())
    account = Account(
        id=str(uuid4()),
        merchant_id=merchant_id,
        xhs_user_id=f"xhs_{uuid4().hex[:8]}",
        nickname="phase2-interaction-smoke",
        access_type="browser",
        status="active",
    )
    db.add(account)
    db.add(
        RiskKeyword(
            merchant_id=None,
            keyword="forbidden",
            category="platform_banned",
            replacement="allowed",
            match_mode="exact",
            severity="block",
            is_active=True,
        )
    )
    await db.flush()

    fake_redis = _FakeRedis()
    with patch("app.services.risk_service.get_redis", return_value=fake_redis), patch(
        "app.services.risk_service.send_alert",
        new=AsyncMock(),
    ):
        blocked = await interaction_service.send_dm(
            merchant_id=merchant_id,
            account_id=account.id,
            content="forbidden outbound text",
            source_record_id=str(uuid4()),
            db=db,
        )
        passed = await interaction_service.send_comment_reply(
            merchant_id=merchant_id,
            account_id=account.id,
            content="thanks for reaching out",
            source_record_id=str(uuid4()),
            db=db,
        )
        await db.commit()

    assert blocked.decision.decision == "blocked"
    assert blocked.delivered is False
    assert blocked.reply_history is None

    assert passed.decision.decision == "passed"
    assert passed.delivered is True
    assert passed.reply_history is not None
    assert isinstance(passed.reply_history, ReplyHistory)

    histories = (
        await db.execute(select(ReplyHistory).where(ReplyHistory.account_id == account.id))
    ).scalars().all()
    assert len(histories) == 1

    logs = (
        await db.execute(
            select(OperationLog)
            .where(OperationLog.account_id == account.id)
            .order_by(OperationLog.created_at.asc())
        )
    ).scalars().all()
    decisions = [item.detail["risk_decision"] for item in logs]
    assert "blocked" in decisions
    assert "passed" in decisions
