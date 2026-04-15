from celery import Celery
from kombu import Exchange, Queue

from app.config import settings

app = Celery(
    "xhs_worker",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=[
        "worker.tasks.publish_task",
        "worker.tasks.data_sync_task",
        "worker.tasks.industry_crawl_task",
        "worker.tasks.trend_analysis_task",
        "worker.tasks.weight_update_task",
        "worker.tasks.account_probe_task",
        "worker.tasks.profile_sync_task",
        "worker.tasks.alert_task",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,  # 任务执行完才 ack，防止丢失
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_default_retry_delay=60,
    # 死信队列配置
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("publish", Exchange("publish"), routing_key="publish"),
        Queue("crawl", Exchange("crawl"), routing_key="crawl"),
    ),
    task_default_queue="default",
)
