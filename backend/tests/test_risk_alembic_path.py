from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import Alert, OperationLog
from app.models.account import Account
from app.models.risk import RiskKeyword
from app.services import risk_service


pytestmark = [pytest.mark.requires_db, pytest.mark.alembic_only]


@pytest.mark.asyncio
async def test_risk_tables_created_via_alembic_match_runtime_writes(
    alembic_db: AsyncSession,
) -> None:
    operation_log_columns = {
        row[0]
        for row in (
            await alembic_db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'operation_logs'
                    """
                )
            )
        ).all()
    }
    alert_columns = {
        row[0]
        for row in (
            await alembic_db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'alerts'
                    """
                )
            )
        ).all()
    }

    assert {
        "merchant_id",
        "account_id",
        "module",
        "operation_type",
        "status",
        "detail",
        "error_code",
    } <= operation_log_columns
    assert "content_snapshot" not in operation_log_columns
    assert {
        "merchant_id",
        "account_id",
        "alert_type",
        "module",
        "severity",
        "is_resolved",
    } <= alert_columns

    merchant_id = str(uuid4())
    account = Account(
        id=str(uuid4()),
        merchant_id=merchant_id,
        xhs_user_id=f"xhs_{uuid4().hex[:8]}",
        nickname="alembic-risk-account",
        access_type="browser",
        status="active",
    )
    alembic_db.add(account)
    alembic_db.add(
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
    await alembic_db.flush()

    with patch("app.services.risk_service.send_alert", new=AsyncMock()) as mocked_alert:
        result = await risk_service.scan_input(
            merchant_id=merchant_id,
            account_id=account.id,
            scene="comment_inbound",
            content="forbidden inbound content",
            db=alembic_db,
        )

    assert result.passed is True
    mocked_alert.assert_awaited_once()

    log_record = (
        await alembic_db.execute(select(OperationLog).order_by(OperationLog.created_at.desc()))
    ).scalar_one()
    alert_record = (
        await alembic_db.execute(select(Alert).order_by(Alert.created_at.desc()))
    ).scalar_one()

    assert log_record.detail["violations"] == ["forbidden"]
    assert log_record.error_code is None
    assert alert_record.alert_type == "inbound_risk_hit"
    assert alert_record.module == "E"
    assert alert_record.is_resolved is False
