"""Risk scan helpers for agent-side executors."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.risk import RiskScanResponse
from app.services import risk_service


async def scan_inbound_content(
    merchant_id: str,
    account_id: str,
    scene: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse:
    """Run inbound risk observation for comments or direct messages."""

    return await risk_service.scan_input(
        merchant_id=merchant_id,
        account_id=account_id,
        scene=scene,
        content=content,
        db=db,
    )


async def scan_outbound_content(
    merchant_id: str,
    account_id: str,
    scene: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse:
    """Run outbound risk checks before automated send actions."""

    return await risk_service.scan_output(
        merchant_id=merchant_id,
        account_id=account_id,
        scene=scene,
        content=content,
        db=db,
    )


def inject_reply_variants(content: str) -> str:
    """Apply lightweight text variants before automated delivery."""

    return risk_service.inject_variants(content)


async def get_humanized_delay(account_id: str, action: str) -> float:
    """Fetch the recommended humanized delay for the executor layer."""

    return await risk_service.apply_humanized_delay(
        account_id=account_id,
        action=action,
    )
