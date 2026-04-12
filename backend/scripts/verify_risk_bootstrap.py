"""Empty-database bootstrap verification for Module E."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.models.analytics import Alert, OperationLog
from app.models.account import Account
from app.models.risk import RiskKeyword
from app.services import risk_service


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    merchant_id = str(uuid4())
    async with session_factory() as session:
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="phase1-bootstrap-check",
            access_type="browser",
            status="active",
        )
        session.add(account)
        session.add(
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
        await session.flush()

        result = await risk_service.scan_input(
            merchant_id=merchant_id,
            account_id=account.id,
            scene="comment_inbound",
            content="forbidden bootstrap content",
            db=session,
        )
        await session.commit()

        log_record = (
            await session.execute(select(OperationLog).order_by(OperationLog.created_at.desc()))
        ).scalars().first()
        alert_record = (
            await session.execute(select(Alert).order_by(Alert.created_at.desc()))
        ).scalars().first()

    await engine.dispose()

    assert result.passed is True
    assert log_record.detail["violations"] == ["forbidden"]
    assert alert_record.alert_type == "inbound_risk_hit"
    print("Module E bootstrap verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
