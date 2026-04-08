from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    queue="crawl",
    name="worker.tasks.data_sync_task.sync_all_notes_data",
)
def sync_all_notes_data(self) -> None:
    """每 24h 回抓所有已发布笔记的互动数据（阅读量/点赞/收藏/评论）。"""
    # TODO: 实现数据回抓逻辑
    raise NotImplementedError
