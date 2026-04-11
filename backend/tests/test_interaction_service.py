from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.risk import ReplyHistory
from app.schemas.risk import RiskScanResponse
from app.services import interaction_service


class TestInteractionRiskIntegration:
    @pytest.mark.asyncio
    async def test_scan_inbound_comment_delegates_to_scan_input(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account_id = str(uuid4())
        expected = RiskScanResponse(
            passed=True,
            decision="passed",
            hits=[],
            retryable=False,
        )

        with patch(
            "app.services.interaction_service.risk_service.scan_input",
            new=AsyncMock(return_value=expected),
        ) as mocked_scan:
            result = await interaction_service.scan_inbound_comment(
                merchant_id=merchant_id,
                account_id=account_id,
                content="hello from comment",
                db=db,
            )

        assert result is expected
        mocked_scan.assert_awaited_once_with(
            merchant_id=merchant_id,
            account_id=account_id,
            scene="comment_inbound",
            content="hello from comment",
            db=db,
        )

    @pytest.mark.asyncio
    async def test_scan_inbound_dm_delegates_to_scan_input(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account_id = str(uuid4())
        expected = RiskScanResponse(
            passed=True,
            decision="passed",
            hits=[],
            retryable=False,
        )

        with patch(
            "app.services.interaction_service.risk_service.scan_input",
            new=AsyncMock(return_value=expected),
        ) as mocked_scan:
            result = await interaction_service.scan_inbound_dm(
                merchant_id=merchant_id,
                account_id=account_id,
                content="hello from dm",
                db=db,
            )

        assert result is expected
        mocked_scan.assert_awaited_once_with(
            merchant_id=merchant_id,
            account_id=account_id,
            scene="dm_inbound",
            content="hello from dm",
            db=db,
        )

    @pytest.mark.asyncio
    async def test_send_comment_reply_persists_history_after_successful_delivery(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="interaction-comment",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        passed = RiskScanResponse(
            passed=True,
            decision="passed",
            hits=[],
            retryable=False,
        )

        with patch(
            "app.services.interaction_service.risk_service.scan_output",
            new=AsyncMock(return_value=passed),
        ) as mocked_scan, patch(
            "app.services.interaction_service._dispatch_outbound_interaction",
            new=AsyncMock(return_value=True),
        ) as mocked_dispatch:
            result = await interaction_service.send_comment_reply(
                merchant_id=merchant_id,
                account_id=account.id,
                content="Thanks for your comment.",
                source_record_id=str(uuid4()),
                db=db,
            )

        assert result.decision.decision == "passed"
        assert result.delivered is True
        assert isinstance(result.reply_history, ReplyHistory)
        assert result.reply_history is not None
        assert result.reply_history.source_type == "comment_reply"
        assert result.reply_history.content == "Thanks for your comment."
        mocked_scan.assert_awaited_once()
        mocked_dispatch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_dm_returns_risk_decision_without_dispatch_when_blocked(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account_id = str(uuid4())
        blocked = RiskScanResponse(
            passed=False,
            decision="blocked",
            hits=[],
            retryable=False,
        )

        with patch(
            "app.services.interaction_service.risk_service.scan_output",
            new=AsyncMock(return_value=blocked),
        ) as mocked_scan, patch(
            "app.services.interaction_service._dispatch_outbound_interaction",
            new=AsyncMock(return_value=True),
        ) as mocked_dispatch, patch(
            "app.services.interaction_service.risk_service.persist_reply_history",
            new=AsyncMock(),
        ) as mocked_history:
            result = await interaction_service.send_dm(
                merchant_id=merchant_id,
                account_id=account_id,
                content="Outbound dm",
                source_record_id=str(uuid4()),
                db=db,
            )

        assert result.decision.decision == "blocked"
        assert result.delivered is False
        assert result.reply_history is None
        mocked_scan.assert_awaited_once()
        mocked_dispatch.assert_not_awaited()
        mocked_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_dm_skips_history_when_delivery_fails_after_risk_pass(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account_id = str(uuid4())
        passed = RiskScanResponse(
            passed=True,
            decision="passed",
            hits=[],
            retryable=False,
        )

        with patch(
            "app.services.interaction_service.risk_service.scan_output",
            new=AsyncMock(return_value=passed),
        ) as mocked_scan, patch(
            "app.services.interaction_service._dispatch_outbound_interaction",
            new=AsyncMock(return_value=False),
        ) as mocked_dispatch, patch(
            "app.services.interaction_service.risk_service.persist_reply_history",
            new=AsyncMock(),
        ) as mocked_history:
            result = await interaction_service.send_dm(
                merchant_id=merchant_id,
                account_id=account_id,
                content="Outbound dm",
                source_record_id=str(uuid4()),
                db=db,
            )

        assert result.decision.decision == "passed"
        assert result.delivered is False
        assert result.reply_history is None
        mocked_scan.assert_awaited_once()
        mocked_dispatch.assert_awaited_once()
        mocked_history.assert_not_awaited()
