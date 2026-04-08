from celery.schedules import crontab

from worker.celery_app import app

app.conf.beat_schedule = {
    # 账号状态探测：每 10 分钟
    "account-probe": {
        "task": "worker.tasks.account_probe_task.probe_all_accounts",
        "schedule": crontab(minute="*/10"),
    },
    # 数据回抓：每 24 小时（凌晨 2 点）
    "data-sync": {
        "task": "worker.tasks.data_sync_task.sync_all_notes_data",
        "schedule": crontab(hour=2, minute=0),
    },
    # 账号画像同步：每 24 小时（凌晨 3 点）
    "profile-sync": {
        "task": "worker.tasks.profile_sync_task.sync_all_profiles",
        "schedule": crontab(hour=3, minute=0),
    },
    # 行业爆款采集：每 24 小时（凌晨 4 点）
    "industry-crawl": {
        "task": "worker.tasks.industry_crawl_task.crawl_industry_notes",
        "schedule": crontab(hour=4, minute=0),
    },
    # 行业趋势分析：每 24 小时（凌晨 5 点）
    "trend-analysis": {
        "task": "worker.tasks.trend_analysis_task.analyze_trends",
        "schedule": crontab(hour=5, minute=0),
    },
    # RAG 权重更新：数据回抓后触发（凌晨 2 点 30 分）
    "weight-update": {
        "task": "worker.tasks.weight_update_task.update_retrieval_weights",
        "schedule": crontab(hour=2, minute=30),
    },
}
