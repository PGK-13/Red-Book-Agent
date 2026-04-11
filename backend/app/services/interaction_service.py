"""Interaction service helpers with risk-control integration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk import ReplyHistory
from app.schemas.risk import RiskScanResponse
from app.services import risk_service


@dataclass(slots=True)
class InteractionDeliveryResult:
    """Outbound interaction result after risk checks and optional delivery."""

    decision: RiskScanResponse
    delivered: bool
    reply_history: ReplyHistory | None = None


async def scan_inbound_comment(
    merchant_id: str,
    account_id: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse:
    """Observe inbound comment content without blocking the workflow."""

    return await risk_service.scan_input(
        merchant_id=merchant_id,
        account_id=account_id,
        scene="comment_inbound",
        content=content,
        db=db,
    )


async def scan_inbound_dm(
    merchant_id: str,
    account_id: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse:
    """Observe inbound direct-message content without blocking the workflow."""

    return await risk_service.scan_input(
        merchant_id=merchant_id,
        account_id=account_id,
        scene="dm_inbound",
        content=content,
        db=db,
    )


async def send_comment_reply(
    merchant_id: str,
    account_id: str,
    content: str,
    db: AsyncSession,
    source_record_id: str | None = None,
) -> InteractionDeliveryResult:
    """Run outbound risk checks before sending a public comment reply."""

    return await _send_outbound_interaction(
        merchant_id=merchant_id,
        account_id=account_id,
        content=content,
        scene="comment_reply",
        source_record_id=source_record_id,
        db=db,
    )


async def send_dm(
    merchant_id: str,
    account_id: str,
    content: str,
    db: AsyncSession,
    source_record_id: str | None = None,
) -> InteractionDeliveryResult:
    """Run outbound risk checks before sending a direct message."""

    return await _send_outbound_interaction(
        merchant_id=merchant_id,
        account_id=account_id,
        content=content,
        scene="dm_send",
        source_record_id=source_record_id,
        db=db,
    )


async def _send_outbound_interaction(
    merchant_id: str,
    account_id: str,
    content: str,
    scene: str,
    source_record_id: str | None,
    db: AsyncSession,
) -> InteractionDeliveryResult:
    decision = await risk_service.scan_output(
        merchant_id=merchant_id,
        account_id=account_id,
        scene=scene,
        content=content,
        db=db,
    )
    if decision.decision != "passed":
        return InteractionDeliveryResult(
            decision=decision,
            delivered=False,
            reply_history=None,
        )

    delivered = await _dispatch_outbound_interaction(
        account_id=account_id,
        scene=scene,
        content=content,
        source_record_id=source_record_id,
    )
    if not delivered:
        return InteractionDeliveryResult(
            decision=decision,
            delivered=False,
            reply_history=None,
        )

    history = await risk_service.persist_reply_history(
        account_id=account_id,
        content=content,
        source_type=scene,
        source_record_id=source_record_id,
        db=db,
    )
    return InteractionDeliveryResult(
        decision=decision,
        delivered=True,
        reply_history=history,
    )


async def _dispatch_outbound_interaction(
    account_id: str,
    scene: str,
    content: str,
    source_record_id: str | None,
) -> bool:
    # TODO: Replace this placeholder with the actual module D sender once the
    # comment-reply and DM executors are implemented.
    _ = (account_id, scene, content, source_record_id)
    return True
