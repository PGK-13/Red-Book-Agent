"""Comment reply executor helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import interaction_service

from agent.tools import risk_scan


@dataclass(slots=True)
class CommentReplyExecutionResult:
    """Execution result for an automated comment reply."""

    content: str
    delay_seconds: float
    delivery: interaction_service.InteractionDeliveryResult


async def execute_comment_reply(
    merchant_id: str,
    account_id: str,
    content: str,
    db: AsyncSession,
    source_record_id: str | None = None,
    sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> CommentReplyExecutionResult:
    """Inject variants, wait with a humanized delay, then send the reply."""

    variant_content = risk_scan.inject_reply_variants(content)
    delay_seconds = await risk_scan.get_humanized_delay(account_id, "comment_reply")
    await sleep_func(delay_seconds)

    delivery = await interaction_service.send_comment_reply(
        merchant_id=merchant_id,
        account_id=account_id,
        content=variant_content,
        source_record_id=source_record_id,
        db=db,
    )
    return CommentReplyExecutionResult(
        content=variant_content,
        delay_seconds=delay_seconds,
        delivery=delivery,
    )
