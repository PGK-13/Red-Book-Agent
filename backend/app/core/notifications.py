import logging

logger = logging.getLogger(__name__)

_SUPPORTED_SEVERITIES = {"info", "warning", "critical"}
_ALERT_QUEUE = "default"


def _normalize_severity(severity: str) -> str:
    normalized = (severity or "warning").strip().lower()
    if normalized not in _SUPPORTED_SEVERITIES:
        return "warning"
    return normalized


def _enqueue_async_alert(payload: dict[str, str]) -> bool:
    try:
        from worker.tasks.alert_task import send_alert as send_alert_task

        send_alert_task.apply_async(kwargs=payload, queue=_ALERT_QUEUE)
        return True
    except Exception:
        logger.warning(
            "Failed to enqueue alert task, falling back to local logging",
            exc_info=True,
        )
        return False


async def send_alert(
    merchant_id: str,
    alert_type: str,
    message: str,
    severity: str = "warning",
) -> None:
    """Dispatch alerts asynchronously and fall back to local logging if needed."""

    payload = {
        "merchant_id": merchant_id,
        "alert_type": alert_type,
        "message": message,
        "severity": _normalize_severity(severity),
    }
    if _enqueue_async_alert(payload):
        logger.info(
            "Queued alert task type=%s merchant=%s severity=%s",
            payload["alert_type"],
            payload["merchant_id"],
            payload["severity"],
        )
        return

    logger.warning(
        "Alert [%s] merchant=%s severity=%s: %s",
        payload["alert_type"],
        payload["merchant_id"],
        payload["severity"],
        payload["message"],
    )
