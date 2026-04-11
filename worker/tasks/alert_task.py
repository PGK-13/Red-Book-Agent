from __future__ import annotations

import logging

from worker.celery_app import app

logger = logging.getLogger(__name__)

_SUPPORTED_SEVERITIES = {"info", "warning", "critical"}
_ALERT_CATALOG = {
    "risk_quota_exceeded": "Risk quota exceeded",
    "competitor_hits_abnormal": "Competitor keyword hits spiked",
    "risk_rewrite_failed": "Risk rewrite retries exhausted",
    "rest_window_violation": "Rest-window scheduling violation",
    "inbound_risk_hit": "Inbound risky content observed",
    "cookie_expired": "Account cookie expired",
    "cookie_expiring": "Account cookie expiring soon",
    "account_banned": "Account banned by platform",
    "account_rate_limited": "Account rate limited by platform",
}


def _normalize_severity(severity: str) -> str:
    normalized = (severity or "warning").strip().lower()
    if normalized not in _SUPPORTED_SEVERITIES:
        return "warning"
    return normalized


def _dispatch_to_channels(payload: dict[str, str]) -> None:
    summary = _ALERT_CATALOG.get(payload["alert_type"], "Generic alert")
    logger.warning(
        "Dispatching alert [%s] merchant=%s severity=%s summary=%s message=%s",
        payload["alert_type"],
        payload["merchant_id"],
        payload["severity"],
        summary,
        payload["message"],
    )


@app.task(
    bind=True,
    max_retries=3,
    name="worker.tasks.alert_task.send_alert",
)
def send_alert(
    self,
    merchant_id: str,
    alert_type: str,
    message: str,
    severity: str = "warning",
) -> dict[str, str]:
    """Asynchronously dispatch merchant-facing alerts."""

    payload = {
        "merchant_id": merchant_id,
        "alert_type": (alert_type or "unknown").strip(),
        "message": message,
        "severity": _normalize_severity(severity),
    }
    try:
        _dispatch_to_channels(payload)
        return payload
    except Exception as exc:
        logger.exception(
            "Alert dispatch failed type=%s merchant=%s retry=%s",
            payload["alert_type"],
            payload["merchant_id"],
            self.request.retries,
        )
        raise self.retry(exc=exc, countdown=min(60 * (self.request.retries + 1), 300))
