from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    queue="crawl",
    name="worker.tasks.industry_crawl_task.crawl_industry_notes",
)
def crawl_industry_notes(self) -> None:
    """每 24h 采集行业爆款笔记（按商家配置的行业关键词）。"""
    # TODO: 实现行业爆款采集逻辑（Playwright）
    raise NotImplementedError
