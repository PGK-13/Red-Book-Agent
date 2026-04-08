import logging

logger = logging.getLogger(__name__)


async def send_alert(
    merchant_id: str,
    alert_type: str,
    message: str,
    severity: str = "warning",
) -> None:
    """
    发送告警通知（Webhook / 邮件）。
    TODO: 接入实际通知渠道。
    """
    logger.warning(
        "Alert [%s] merchant=%s severity=%s: %s",
        alert_type,
        merchant_id,
        severity,
        message,
    )
