"""账号管理 ORM 模型：Account、AccountPersona、ProxyConfig。"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base

# ── Enum 定义 ──

access_type_enum = Enum(
    "oauth", "rpa", "browser",
    name="access_type_enum",
)

account_status_enum = Enum(
    "active", "suspended", "auth_expired", "banned",
    name="account_status_enum",
)


# ── Account ──

class Account(Base):
    """小红书账号主表。"""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("merchant_id", "xhs_user_id", name="uq_merchant_xhs_user"),
        Index("ix_accounts_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), index=True, nullable=False
    )
    xhs_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    nickname: Mapped[str] = mapped_column(String(128), nullable=False)
    access_type: Mapped[str] = mapped_column(access_type_enum, nullable=False)
    oauth_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookie_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookie_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        account_status_enum, nullable=False, server_default="active"
    )
    last_probed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──
    persona: Mapped[AccountPersona | None] = relationship(
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )
    proxy_config: Mapped[ProxyConfig | None] = relationship(
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ── AccountPersona ──

class AccountPersona(Base):
    """账号人设配置（一对一）。"""

    __tablename__ = "account_personas"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}", nullable=False)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_synced_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="persona")


# ── ProxyConfig ──

class ProxyConfig(Base):
    """代理与设备指纹配置（一对一）。"""

    __tablename__ = "proxy_configs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    proxy_url: Mapped[str] = mapped_column(Text, nullable=False)  # 加密存储
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    screen_resolution: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Asia/Shanghai"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    account: Mapped[Account] = relationship(back_populates="proxy_config")
