from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    name="worker.tasks.profile_sync_task.sync_all_profiles",
)
def sync_all_profiles(self) -> None:
    """每 24h 同步账号画像（粉丝数、简介、标签等）。"""
    # TODO: 实现账号画像同步逻辑（Playwright 抓取小红书个人主页）
    raise NotImplementedError
