"""Risk control API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentMerchantId, DbSession
from app.schemas.base import BaseResponse
from app.schemas.risk import (
    AccountRiskQuotaResponse,
    AccountRiskScheduleRequest,
    RiskEventResponse,
    RiskKeywordCreateRequest,
    RiskKeywordResponse,
    RiskKeywordUpdateRequest,
    RiskScanRequest,
    RiskScanResponse,
)
from app.services import risk_service

router = APIRouter(prefix="/risk", tags=["风控"])


@router.get("/keywords", response_model=BaseResponse[list[RiskKeywordResponse]])
async def list_keywords(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    category: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> BaseResponse[list[RiskKeywordResponse]]:
    """List risk keywords visible to the current merchant."""

    keywords = await risk_service.list_keywords(
        merchant_id=merchant_id,
        category=category,
        is_active=is_active,
        db=db,
    )
    return BaseResponse(data=[_to_keyword_response(item) for item in keywords])


@router.post("/keywords", response_model=BaseResponse[RiskKeywordResponse])
async def create_keyword(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: RiskKeywordCreateRequest,
) -> BaseResponse[RiskKeywordResponse]:
    """Create a merchant-owned risk keyword."""

    keyword = await risk_service.create_keyword(merchant_id=merchant_id, data=body, db=db)
    return BaseResponse(data=_to_keyword_response(keyword))


@router.put("/keywords/{keyword_id}", response_model=BaseResponse[RiskKeywordResponse])
async def update_keyword(
    keyword_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: RiskKeywordUpdateRequest,
) -> BaseResponse[RiskKeywordResponse]:
    """Update a merchant-owned risk keyword."""

    keyword = await risk_service.update_keyword(
        merchant_id=merchant_id,
        keyword_id=str(keyword_id),
        data=body,
        db=db,
    )
    return BaseResponse(data=_to_keyword_response(keyword))


@router.delete("/keywords/{keyword_id}", response_model=BaseResponse)
async def delete_keyword(
    keyword_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """Delete a merchant-owned risk keyword."""

    await risk_service.delete_keyword(
        merchant_id=merchant_id,
        keyword_id=str(keyword_id),
        db=db,
    )
    return BaseResponse(message="风险关键词已删除")


@router.post("/scan", response_model=BaseResponse[RiskScanResponse])
async def scan_content(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: RiskScanRequest,
) -> BaseResponse[RiskScanResponse]:
    """Run a manual risk scan for inbound or outbound content."""

    if body.scene in {"comment_inbound", "dm_inbound"}:
        result = await risk_service.scan_input(
            merchant_id=merchant_id,
            account_id=str(body.account_id),
            scene=body.scene,
            content=body.content,
            db=db,
        )
    else:
        result = await risk_service.scan_output(
            merchant_id=merchant_id,
            account_id=str(body.account_id),
            scene=body.scene,
            content=body.content,
            db=db,
        )
    return BaseResponse(data=result)


@router.get(
    "/accounts/{account_id}/quota",
    response_model=BaseResponse[AccountRiskQuotaResponse],
)
async def get_account_quota(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[AccountRiskQuotaResponse]:
    """Get current quota usage and rest-window state for one account."""

    quota = await risk_service.get_account_quota(
        merchant_id=merchant_id,
        account_id=str(account_id),
        db=db,
    )
    return BaseResponse(data=quota)


@router.put("/accounts/{account_id}/schedule", response_model=BaseResponse)
async def update_account_schedule(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: AccountRiskScheduleRequest,
) -> BaseResponse:
    """Update account rest-window configuration."""

    await risk_service.update_account_schedule(
        merchant_id=merchant_id,
        account_id=str(account_id),
        data=body,
        db=db,
    )
    return BaseResponse(message="账号休息时段已更新")


@router.get(
    "/accounts/{account_id}/events",
    response_model=BaseResponse[list[RiskEventResponse]],
)
async def list_account_events(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> BaseResponse[list[RiskEventResponse]]:
    """List recent risk events for one account."""

    events = await risk_service.list_account_events(
        merchant_id=merchant_id,
        account_id=str(account_id),
        db=db,
        limit=limit,
    )
    return BaseResponse(data=events)


def _to_keyword_response(keyword) -> RiskKeywordResponse:
    return RiskKeywordResponse(
        id=keyword.id,
        merchant_id=keyword.merchant_id,
        keyword=keyword.keyword,
        category=keyword.category,
        replacement=keyword.replacement,
        match_mode=keyword.match_mode,
        severity=keyword.severity,
        is_active=keyword.is_active,
        created_at=keyword.created_at,
    )
