from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core import notifications


class TestNotifications:
    @pytest.mark.asyncio
    async def test_send_alert_enqueues_celery_task(self) -> None:
        with patch("worker.tasks.alert_task.send_alert.apply_async") as mocked_apply_async:
            await notifications.send_alert(
                merchant_id="merchant-1",
                alert_type="risk_quota_exceeded",
                message="quota exceeded",
                severity="warning",
            )

        mocked_apply_async.assert_called_once_with(
            kwargs={
                "merchant_id": "merchant-1",
                "alert_type": "risk_quota_exceeded",
                "message": "quota exceeded",
                "severity": "warning",
            },
            queue="default",
        )

    @pytest.mark.asyncio
    async def test_send_alert_falls_back_to_local_logging_when_enqueue_fails(self) -> None:
        with patch(
            "worker.tasks.alert_task.send_alert.apply_async",
            side_effect=RuntimeError("broker unavailable"),
        ):
            await notifications.send_alert(
                merchant_id="merchant-1",
                alert_type="risk_quota_exceeded",
                message="quota exceeded",
                severity="warning",
            )
