"""公开扫码登录 API 路由（无认证）。

路由层只做参数校验和响应封装，所有业务逻辑委托给 account_service。
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Query

from app.schemas.account import (
    CaptchaSubmitRequest,
    CaptchaSubmitResponse,
    PublicQrLoginStatusResponse,
    QrLoginStartResponse,
)
from app.schemas.base import BaseResponse
from app.services import account_service

router = APIRouter(prefix="/accounts/qr-login", tags=["扫码登录（公开）"])


@router.post("/start", response_model=BaseResponse[QrLoginStartResponse])
async def public_start_qr_login() -> BaseResponse[QrLoginStartResponse]:
    """启动公开扫码登录，返回二维码图片和 session_id。"""
    result = await account_service.public_start_qr_login()
    return BaseResponse(data=QrLoginStartResponse(**result))


@router.get("/status", response_model=BaseResponse[PublicQrLoginStatusResponse])
async def public_poll_qr_login_status(
    session_id: str = Query(..., description="扫码会话 ID"),
) -> BaseResponse[PublicQrLoginStatusResponse]:
    """轮询公开扫码登录状态。"""
    result = await account_service.public_poll_qr_login_status(session_id)
    return BaseResponse(data=PublicQrLoginStatusResponse(**result))


@router.post("/submit-captcha", response_model=BaseResponse[CaptchaSubmitResponse])
async def public_submit_captcha(
    req: CaptchaSubmitRequest,
) -> BaseResponse[CaptchaSubmitResponse]:
    """提交短信验证码，后端在 Playwright 中填入并提交。"""
    result = await account_service.public_submit_captcha(
        session_id=req.session_id,
        captcha=req.captcha,
    )
    return BaseResponse(
        data=CaptchaSubmitResponse(status=result["status"]),  # type: ignore[arg-type]
    )
