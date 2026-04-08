from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    name="worker.tasks.alert_task.send_alert",
)
def send_alert(self, merchant_id: str, alert_type: str, message: str, severity: str = "warning") -> None:
    """异步发送告警通知。"""
    # TODO: 接入实际通知渠道（Webhook / 邮件 / 短信）
    raise NotImplementedError
