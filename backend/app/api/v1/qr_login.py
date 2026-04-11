"""公开扫码登录 API 路由。

无需认证的公开路由，供前端登录页（QrLoginCard 组件）使用。
路由层只做参数校验和响应封装，所有业务逻辑委托给 account_service。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.account import (
    PublicQrLoginStatusResponse,
    QrLoginStartResponse,
    UserInfo,
)
from app.schemas.base import BaseResponse
from app.services import account_service

router = APIRouter(prefix="/accounts/qr-login", tags=["扫码登录（公开）"])


@router.post("/start", response_model=BaseResponse[QrLoginStartResponse])
async def public_start_qr_login() -> BaseResponse[QrLoginStartResponse]:
    """启动公开扫码登录，返回二维码图片和 session_id。"""
    result = await account_service.public_start_qr_login()
    return BaseResponse(
        data=QrLoginStartResponse(
            session_id=result["session_id"],
            qr_image_base64=result["qr_image_base64"],
        )
    )


@router.get("/status", response_model=BaseResponse[PublicQrLoginStatusResponse])
async def public_poll_qr_login_status(
    session_id: str = Query(..., description="扫码会话 ID"),
) -> BaseResponse[PublicQrLoginStatusResponse]:
    """轮询公开扫码登录状态。"""
    result = await account_service.public_poll_qr_login_status(session_id)
    user = None
    if result.get("user") is not None:
        user = UserInfo(**result["user"])
    return BaseResponse(
        data=PublicQrLoginStatusResponse(
            status=result["status"],
            token=result.get("token"),
            user=user,
        )
    )
