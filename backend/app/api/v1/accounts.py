"""账号管理 API 路由。

路由层只做参数校验和响应封装，所有业务逻辑委托给 AccountService。
所有路由注入 CurrentMerchantId 和 DbSession 依赖，确保商家数据隔离。
"""

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


def _to_account_response(account: object) -> AccountResponse:
    """将 ORM Account 对象转换为 AccountResponse。"""
    persona = None
    if account.persona is not None:  # type: ignore[union-attr]
        persona = PersonaResponse(
            tone=account.persona.tone,  # type: ignore[union-attr]
            bio=account.persona.bio,  # type: ignore[union-attr]
            tags=account.persona.tags or [],  # type: ignore[union-attr]
            follower_count=account.persona.follower_count,  # type: ignore[union-attr]
            profile_synced_at=account.persona.profile_synced_at,  # type: ignore[union-attr]
        )

    proxy = None
    if account.proxy_config is not None:  # type: ignore[union-attr]
        proxy = ProxyResponse(
            user_agent=account.proxy_config.user_agent,  # type: ignore[union-attr]
            screen_resolution=account.proxy_config.screen_resolution,  # type: ignore[union-attr]
            timezone=account.proxy_config.timezone,  # type: ignore[union-attr]
            is_active=account.proxy_config.is_active,  # type: ignore[union-attr]
        )

    return AccountResponse(
        id=account.id,  # type: ignore[union-attr]
        merchant_id=account.merchant_id,  # type: ignore[union-attr]
        xhs_user_id=account.xhs_user_id,  # type: ignore[union-attr]
        nickname=account.nickname,  # type: ignore[union-attr]
        access_type=account.access_type,  # type: ignore[union-attr]
        status=account.status,  # type: ignore[union-attr]
        cookie_expires_at=account.cookie_expires_at,  # type: ignore[union-attr]
        last_probed_at=account.last_probed_at,  # type: ignore[union-attr]
        created_at=account.created_at,  # type: ignore[union-attr]
        persona=persona,
        proxy=proxy,
    )


# ── GET /accounts ──


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
    return PaginatedResponse[AccountResponse](
        data=PaginatedData[AccountResponse](
            items=[_to_account_response(a) for a in items],
            next_cursor=str(next_cursor) if next_cursor else None,
            has_more=has_more,
        )
    )


# ── POST /accounts ──


@router.post("", response_model=BaseResponse[AccountResponse], status_code=201)
async def create_account(
    body: AccountCreateRequest,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[AccountResponse]:
    """新增账号。"""
    account = await account_service.create_account(merchant_id, body, db)
    await db.commit()
    await db.refresh(account, ["persona", "proxy_config"])
    return BaseResponse[AccountResponse](data=_to_account_response(account))


# ── GET /accounts/{id} ──


@router.get("/{account_id}", response_model=BaseResponse[AccountResponse])
async def get_account(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[AccountResponse]:
    """获取账号详情。"""
    account = await account_service.get_account(merchant_id, str(account_id), db)
    return BaseResponse[AccountResponse](data=_to_account_response(account))


# ── DELETE /accounts/{id} ──


@router.delete("/{account_id}", response_model=BaseResponse)
async def delete_account(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """删除账号（级联删除 persona、proxy_config）。"""
    await account_service.delete_account(merchant_id, str(account_id), db)
    await db.commit()
    return BaseResponse(message="账号已删除")


# ── POST /accounts/{id}/oauth/callback ──


@router.post("/{account_id}/oauth/callback", response_model=BaseResponse)
async def oauth_callback(
    account_id: UUID,
    body: OAuthCallbackRequest,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """OAuth 2.0 授权回调。"""
    await account_service.handle_oauth_callback(
        merchant_id, str(account_id), body.code, db
    )
    await db.commit()
    return BaseResponse(message="OAuth 授权成功")


# ── PUT /accounts/{id}/cookie ──


@router.put("/{account_id}/cookie", response_model=BaseResponse)
async def update_cookie(
    account_id: UUID,
    body: CookieUpdateRequest,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """更新账号 Cookie。"""
    await account_service.update_cookie(
        merchant_id, str(account_id), body.raw_cookie, body.expires_at, db
    )
    await db.commit()
    return BaseResponse(message="Cookie 已更新")


# ── GET /accounts/{id}/status ──


@router.get(
    "/{account_id}/status", response_model=BaseResponse[AccountStatusResponse]
)
async def get_account_status(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[AccountStatusResponse]:
    """获取账号当前状态。"""
    account = await account_service.get_account(merchant_id, str(account_id), db)

    cookie_remaining_hours: float | None = None
    if account.cookie_expires_at is not None:
        remaining = (
            account.cookie_expires_at - datetime.now(timezone.utc)
        ).total_seconds() / 3600
        cookie_remaining_hours = max(remaining, 0.0)

    return BaseResponse[AccountStatusResponse](
        data=AccountStatusResponse(
            status=account.status,
            last_probed_at=account.last_probed_at,
            cookie_expires_at=account.cookie_expires_at,
            cookie_remaining_hours=cookie_remaining_hours,
        )
    )


# ── POST /accounts/{id}/sync-profile ──


@router.post("/{account_id}/sync-profile", response_model=BaseResponse)
async def sync_profile(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """手动触发账号画像同步。"""
    await account_service.sync_profile(merchant_id, str(account_id), db)
    await db.commit()
    return BaseResponse(message="画像同步完成")


# ── PUT /accounts/{id}/persona ──


@router.put("/{account_id}/persona", response_model=BaseResponse)
async def update_persona(
    account_id: UUID,
    body: PersonaUpdateRequest,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """更新账号人设配置。"""
    await account_service.update_persona(merchant_id, str(account_id), body, db)
    await db.commit()
    return BaseResponse(message="人设已更新")


# ── PUT /accounts/{id}/proxy ──


@router.put("/{account_id}/proxy", response_model=BaseResponse)
async def update_proxy(
    account_id: UUID,
    body: ProxyUpdateRequest,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse:
    """更新代理配置。"""
    await account_service.update_proxy(merchant_id, str(account_id), body, db)
    await db.commit()
    return BaseResponse(message="代理配置已更新")


# ── POST /accounts/{id}/qr-login/start ──


@router.post(
    "/{account_id}/qr-login/start",
    response_model=BaseResponse[QrLoginStartResponse],
)
async def start_qr_login(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
) -> BaseResponse[QrLoginStartResponse]:
    """启动扫码登录，返回二维码图片和 session_id。"""
    result = await account_service.start_qr_login(
        merchant_id, str(account_id), db
    )
    return BaseResponse[QrLoginStartResponse](
        data=QrLoginStartResponse(
            session_id=result["session_id"],
            qr_image_base64=result["qr_image_base64"],
        )
    )


# ── GET /accounts/{id}/qr-login/status ──


@router.get(
    "/{account_id}/qr-login/status",
    response_model=BaseResponse[QrLoginStatusResponse],
)
async def poll_qr_login_status(
    account_id: UUID,
    merchant_id: CurrentMerchantId,
    db: DbSession,
    session_id: str = Query(..., description="扫码会话 ID"),
) -> BaseResponse[QrLoginStatusResponse]:
    """轮询扫码登录状态。"""
    result = await account_service.poll_qr_login_status(
        merchant_id, str(account_id), session_id, db
    )
    return BaseResponse[QrLoginStatusResponse](
        data=QrLoginStatusResponse(status=result["status"])
    )
