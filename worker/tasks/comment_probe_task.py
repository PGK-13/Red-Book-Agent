"""评论探测任务 — CommentProbeTask。

Celery Beat 定时触发（建议每 10 秒检查一次令牌桶）。
调用 NotePollingScheduler 决定是否需要执行检查，每次最多处理 batch_size 篇笔记。
"""

from worker.celery_app import app

from app.services.note_polling_scheduler import NotePollingScheduler


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="worker.tasks.comment_probe_task.probe_monitored_notes",
)
async def probe_monitored_notes(self, account_id: str | None = None) -> dict:
    """探测所有监测笔记的新评论。

    由 Celery Beat 每 10 秒触发一次。
    通过 NotePollingScheduler 控制探测频率，避免固定模式检测。

    Args:
        account_id: 可选，指定账号 ID。不指定则遍历所有活跃账号。

    Returns:
        探测结果统计。
    """
    # TODO: 实现完整探测逻辑
    #
    # 1. 若 account_id 指定，只处理该账号：
    #    - 查询 monitored_notes WHERE account_id = account_id AND is_active = true
    # 2. 若未指定，遍历所有有监测笔记的账号
    #
    # 3. 对每条 monitored_note:
    #    - 检查 captcha 阻断标志 is_captcha_blocked(account_id)
    #    - 检查账号状态
    #    - 调用 NotePollingScheduler.run_batch() 执行增量评论检测
    #    - 对增量评论：
    #      - perform_ocr（如有图片）
    #      - classify_comment_intent()
    #      - 如需 HITL，enqueue_hitl()
    #      - 如触发私信，record_dm_trigger + send_dm_via_rpa
    #    - 更新 monitored_note.last_checked_at 和 last_known_comment_count
    #
    # 4. 返回统计：processed_notes, new_comments, triggered_dms

    return {
        "account_id": account_id,
        "processed_notes": 0,
        "new_comments": 0,
        "triggered_dms": 0,
        "status": "ok",
    }


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="worker.tasks.comment_probe_task.probe_single_note",
)
async def probe_single_note(self, note_id: str, account_id: str) -> dict:
    """探测单篇笔记的新评论。

    供手动触发或单独监控使用。

    Args:
        note_id: 笔记 ID（monitored_notes 表主键）。
        account_id: 账号 ID。

    Returns:
        探测结果。
    """
    # TODO: 实现单篇笔记探测逻辑
    #
    # 1. 查询 monitored_notes WHERE id = note_id
    # 2. 检查账号状态和 captcha 标志
    # 3. 调用 playwright_comment_monitor.poll_note_comments()
    # 4. 处理新增评论（OCR、意图分类、去重、HITL 或触发私信）
    # 5. 更新 last_checked_at 和 last_known_comment_count

    return {
        "note_id": note_id,
        "account_id": account_id,
        "new_comments": 0,
        "status": "ok",
    }
