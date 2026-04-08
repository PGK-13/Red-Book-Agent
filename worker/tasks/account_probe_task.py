from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    name="worker.tasks.account_probe_task.probe_all_accounts",
)
def probe_all_accounts(self) -> None:
    """每 10min 探测所有账号状态，检测 Cookie 过期、封号等异常。"""
    # TODO: 实现账号状态探测逻辑
    # - Cookie 距过期 <24h → 触发预警通知
    # - Cookie 已过期 → 更新状态为 auth_expired
    # - 账号被封 → 更新状态为 banned，触发告警
    raise NotImplementedError
