"""账号模块请求/响应 Schema。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── 请求 Schema ──


class AccountCreateRequest(BaseModel):
    """新增账号请求。"""

    xhs_user_id: str = Field(..., max_length=64)
    nickname: str = Field(..., max_length=128)
    access_type: Literal["oauth", "rpa", "browser"]


class OAuthCallbackRequest(BaseModel):
    """OAuth 2.0 授权回调请求。"""

    code: str = Field(..., description="OAuth 授权码")


class CookieUpdateRequest(BaseModel):
    """更新账号 Cookie 请求。"""

    raw_cookie: str = Field(..., description="原始 Cookie 字符串")
    expires_at: datetime = Field(..., description="Cookie 过期时间")


class PersonaUpdateRequest(BaseModel):
    """更新账号人设请求。"""

    tone: str | None = Field(None, max_length=64)
    system_prompt: str | None = None
    bio: str | None = None
    tags: list[str] | None = None


class ProxyUpdateRequest(BaseModel):
    """更新代理配置请求。"""

    proxy_url: str = Field(..., description="代理地址（含认证信息）")
    user_agent: str
    screen_resolution: str = Field(..., pattern=r"^\d+x\d+$")
    timezone: str = Field(default="Asia/Shanghai")
    is_active: bool = True


# ── 响应 Schema ──


class PersonaResponse(BaseModel):
    """账号人设响应。"""

    tone: str | None = None
    bio: str | None = None
    tags: list[str] = Field(default_factory=list)
    follower_count: int | None = None
    profile_synced_at: datetime | None = None


class ProxyResponse(BaseModel):
    """代理配置响应（不返回 proxy_url，安全考虑）。"""

    user_agent: str
    screen_resolution: str
    timezone: str
    is_active: bool


class AccountResponse(BaseModel):
    """账号详情响应。"""

    id: UUID
    merchant_id: UUID
    xhs_user_id: str
    nickname: str
    access_type: str
    status: str
    cookie_expires_at: datetime | None = None
    last_probed_at: datetime | None = None
    created_at: datetime
    persona: PersonaResponse | None = None
    proxy: ProxyResponse | None = None


class AccountStatusResponse(BaseModel):
    """账号状态响应。"""

    status: str
    last_probed_at: datetime | None = None
    cookie_expires_at: datetime | None = None
    cookie_remaining_hours: float | None = None


class QrLoginStartResponse(BaseModel):
    """扫码登录启动响应。"""

    session_id: str
    qr_image_base64: str


class QrLoginStatusResponse(BaseModel):
    """扫码登录状态轮询响应。"""

    status: Literal["waiting", "success", "expired"]


class UserInfo(BaseModel):
    """用户信息（JWT 签发后返回给前端）。"""

    nickname: str
    avatar: str | None = None
    xhs_user_id: str


class PublicQrLoginStatusResponse(BaseModel):
    """公开扫码登录状态轮询响应。"""

    status: Literal["waiting", "success", "expired"]
    token: str | None = None
    user: UserInfo | None = None
