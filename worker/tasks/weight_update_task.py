from worker.celery_app import app


@app.task(
    bind=True,
    max_retries=3,
    name="worker.tasks.weight_update_task.update_retrieval_weights",
)
def update_retrieval_weights(self) -> None:
    """
    更新 RAG 检索权重。
    规则：互动率 > 均值×1.5 → weight×1.2（上限 5.0）
          互动率 < 均值×0.5 → weight×0.9（下限 0.1）
    """
    # TODO: 实现权重更新逻辑，同步更新 PostgreSQL + Qdrant payload
    raise NotImplementedError
