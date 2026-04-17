from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.risk import RiskScanResponse
from app.services.interaction_service import InteractionDeliveryResult

from agent.tools import comment_reply, dm_sender, risk_scan


class TestRiskScanTool:
    @pytest.mark.asyncio
    async def test_scan_inbound_content_delegates_to_risk_service(self) -> None:
        expected = RiskScanResponse(
            passed=True,
            decision="passed",
            hits=[],
            retryable=False,
        )

        with patch(
            "agent.tools.risk_scan.risk_service.scan_input",
            new=AsyncMock(return_value=expected),
        ) as mocked_scan:
            result = await risk_scan.scan_inbound_content(
                merchant_id=str(uuid4()),
                account_id=str(uuid4()),
                scene="comment_inbound",
                content="hello",
                db=AsyncMock(),
            )

        assert result is expected
        mocked_scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_humanized_delay_delegates_to_risk_service(self) -> None:
        with patch(
            "agent.tools.risk_scan.risk_service.apply_humanized_delay",
            new=AsyncMock(return_value=4.2),
        ) as mocked_delay:
            delay = await risk_scan.get_humanized_delay(
                account_id=str(uuid4()),
                action="comment_reply",
            )

        assert delay == 4.2
        mocked_delay.assert_awaited_once()

    def test_inject_reply_variants_uses_risk_service_helper(self) -> None:
        with patch(
            "agent.tools.risk_scan.risk_service.inject_variants",
            return_value="variant text",
        ) as mocked_inject:
            result = risk_scan.inject_reply_variants("original text")

        assert result == "variant text"
        mocked_inject.assert_called_once_with("original text")


class TestExecutorTools:
    @pytest.mark.asyncio
    async def test_execute_comment_reply_consumes_variants_delay_and_delivery(self) -> None:
        delivery = InteractionDeliveryResult(
            decision=RiskScanResponse(
                passed=True,
                decision="passed",
                hits=[],
                retryable=False,
            ),
            delivered=True,
            reply_history=None,
        )
        mocked_sleep = AsyncMock()

        with patch(
            "agent.tools.comment_reply.risk_scan.inject_reply_variants",
            return_value="variant reply",
        ) as mocked_variants, patch(
            "agent.tools.comment_reply.risk_scan.get_humanized_delay",
            new=AsyncMock(return_value=6.5),
        ) as mocked_delay, patch(
            "agent.tools.comment_reply.interaction_service.send_comment_reply",
            new=AsyncMock(return_value=delivery),
        ) as mocked_send:
            result = await comment_reply.execute_comment_reply(
                merchant_id=str(uuid4()),
                account_id=str(uuid4()),
                content="raw reply",
                db=AsyncMock(),
                source_record_id=str(uuid4()),
                sleep_func=mocked_sleep,
            )

        assert result.content == "variant reply"
        assert result.delay_seconds == 6.5
        assert result.delivery is delivery
        mocked_variants.assert_called_once_with("raw reply")
        mocked_delay.assert_awaited_once()
        mocked_sleep.assert_awaited_once_with(6.5)
        mocked_send.assert_awaited_once()
        assert mocked_send.await_args.kwargs["content"] == "variant reply"

    @pytest.mark.asyncio
    async def test_execute_dm_send_consumes_variants_delay_and_delivery(self) -> None:
        delivery = InteractionDeliveryResult(
            decision=RiskScanResponse(
                passed=True,
                decision="passed",
                hits=[],
                retryable=False,
            ),
            delivered=True,
            reply_history=None,
        )
        mocked_sleep = AsyncMock()

        with patch(
            "agent.tools.dm_sender.risk_scan.inject_reply_variants",
            return_value="variant dm",
        ) as mocked_variants, patch(
            "agent.tools.dm_sender.risk_scan.get_humanized_delay",
            new=AsyncMock(return_value=8.1),
        ) as mocked_delay, patch(
            "agent.tools.dm_sender.interaction_service.send_dm",
            new=AsyncMock(return_value=delivery),
        ) as mocked_send:
            result = await dm_sender.execute_dm_send(
                merchant_id=str(uuid4()),
                account_id=str(uuid4()),
                content="raw dm",
                db=AsyncMock(),
                source_record_id=str(uuid4()),
                sleep_func=mocked_sleep,
            )

        assert result.content == "variant dm"
        assert result.delay_seconds == 8.1
        assert result.delivery is delivery
        mocked_variants.assert_called_once_with("raw dm")
        mocked_delay.assert_awaited_once()
        mocked_sleep.assert_awaited_once_with(8.1)
        mocked_send.assert_awaited_once()
        assert mocked_send.await_args.kwargs["content"] == "variant dm"
