"""账号管理 API 路由。

路由层只做参数校验和响应封装，所有业务逻辑委托给 AccountService。
所有路由注入 CurrentMerchantId 和 DbSession 依赖。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentMerchantId, DbSession
from app.schemas.account import (
    AccountCreateRequest,
    AccountResponse,
    AccountStatusResponse,
    CookieUpdateRequest,
    OAuthCallbackRequest,
    PersonaResponse,
    PersonaUpdateRequest,
    ProxyResponse,
    ProxyUpdateRequest,
    QrLoginStartResponse,
    QrLoginStatusResponse,
)
from app.schemas.base import BaseResponse, PaginatedData, PaginatedResponse
from app.services import account_service

router = APIRouter(prefix="/accounts", tags=["账号管理"])


# ── 账号 CRUD ──


@router.get("", response_model=PaginatedResponse[AccountResponse])
async def list_accounts(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PaginatedResponse[AccountResponse]:
    """获取商家所有账号列表（cursor 分页）。"""
    items, next_cursor, has_more = await account_service.list_accounts(
        merchant_id, limit, cursor, db
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[_to_account_response(a) for a in items],
            next_cursor=next_cursor,
            has_more=has_more,
        )
    )


@router.post("", response_model=BaseResponse[AccountResponse])
async def create_account(
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: AccountCreateRequest,
) -> BaseResponse[AccountResponse]:
    """新增账号。"""
    account = await account_service.create_account(merchant_id, body, db)
    return BaseResponse(data=_to_account_response(account))


@router.get("/{account_id}", response_model=BaseResponse[AccountResponse])
async def get_account(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[AccountResponse]:
    """获取账号详情。"""
    account = await account_service.get_account(merchant_id, account_id, db)
    return BaseResponse(data=_to_account_response(account))


@router.delete("/{account_id}", response_model=BaseResponse)
async def delete_account(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """删除账号（级联删除 persona、proxy_config）。"""
    await account_service.delete_account(merchant_id, account_id, db)
    return BaseResponse(message="账号已删除")


# ── 授权管理 ──


@router.post("/{account_id}/oauth/callback", response_model=BaseResponse)
async def oauth_callback(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: OAuthCallbackRequest,
) -> BaseResponse:
    """OAuth 2.0 授权回调。"""
    await account_service.handle_oauth_callback(merchant_id, account_id, body.code, db)
    return BaseResponse(message="OAuth 授权成功")


@router.put("/{account_id}/cookie", response_model=BaseResponse)
async def update_cookie(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: CookieUpdateRequest,
) -> BaseResponse:
    """更新账号 Cookie。"""
    await account_service.update_cookie(
        merchant_id, account_id, body.raw_cookie, body.expires_at, db
    )
    return BaseResponse(message="Cookie 已更新")


# ── 状态 ──


@router.get("/{account_id}/status", response_model=BaseResponse[AccountStatusResponse])
async def get_account_status(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[AccountStatusResponse]:
    """获取账号当前状态。"""
    account = await account_service.get_account(merchant_id, account_id, db)
    remaining: float | None = None
    if account.cookie_expires_at is not None:
        delta = account.cookie_expires_at - datetime.now(timezone.utc)
        remaining = max(delta.total_seconds() / 3600, 0.0)
    return BaseResponse(
        data=AccountStatusResponse(
            status=account.status,
            last_probed_at=account.last_probed_at,
            cookie_expires_at=account.cookie_expires_at,
            cookie_remaining_hours=remaining,
        )
    )


# ── 画像同步 ──


@router.post("/{account_id}/sync-profile", response_model=BaseResponse)
async def sync_profile(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """手动触发画像同步。"""
    await account_service.sync_profile(merchant_id, account_id, db)
    return BaseResponse(message="画像同步完成")


# ── 人设与代理 ──


@router.put("/{account_id}/persona", response_model=BaseResponse)
async def update_persona(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: PersonaUpdateRequest,
) -> BaseResponse:
    """更新账号人设。"""
    await account_service.update_persona(merchant_id, account_id, body, db)
    return BaseResponse(message="人设已更新")


@router.put("/{account_id}/proxy", response_model=BaseResponse)
async def update_proxy(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    body: ProxyUpdateRequest,
) -> BaseResponse:
    """更新代理配置。"""
    await account_service.update_proxy(merchant_id, account_id, body, db)
    return BaseResponse(message="代理配置已更新")


# ── 扫码登录 ──


@router.post(
    "/{account_id}/qr-login/start",
    response_model=BaseResponse[QrLoginStartResponse],
)
async def start_qr_login(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[QrLoginStartResponse]:
    """启动扫码登录，返回二维码图片和 session_id。"""
    result = await account_service.start_qr_login(merchant_id, account_id, db)
    return BaseResponse(
        data=QrLoginStartResponse(
            session_id=result["session_id"],
            qr_image_base64=result["qr_image_base64"],
        )
    )


@router.get(
    "/{account_id}/qr-login/status",
    response_model=BaseResponse[QrLoginStatusResponse],
)
async def poll_qr_login_status(
    account_id: str,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    session_id: str = Query(...),
) -> BaseResponse[QrLoginStatusResponse]:
    """轮询扫码登录状态。"""
    result = await account_service.poll_qr_login_status(
        merchant_id, account_id, session_id, db
    )
    return BaseResponse(data=QrLoginStatusResponse(status=result["status"]))  # type: ignore[arg-type]


# ── 响应转换辅助 ──


def _to_account_response(account) -> AccountResponse:
    """将 ORM Account 对象转换为 AccountResponse schema。"""
    persona: PersonaResponse | None = None
    if account.persona is not None:
        persona = PersonaResponse(
            tone=account.persona.tone,
            bio=account.persona.bio,
            tags=account.persona.tags or [],
            follower_count=account.persona.follower_count,
            profile_synced_at=account.persona.profile_synced_at,
        )

    proxy: ProxyResponse | None = None
    if account.proxy_config is not None:
        proxy = ProxyResponse(
            user_agent=account.proxy_config.user_agent,
            screen_resolution=account.proxy_config.screen_resolution,
            timezone=account.proxy_config.timezone,
            is_active=account.proxy_config.is_active,
        )

    return AccountResponse(
        id=account.id,
        merchant_id=account.merchant_id,
        xhs_user_id=account.xhs_user_id,
        nickname=account.nickname,
        access_type=account.access_type,
        status=account.status,
        cookie_expires_at=account.cookie_expires_at,
        last_probed_at=account.last_probed_at,
        created_at=account.created_at,
        persona=persona,
        proxy=proxy,
    )
