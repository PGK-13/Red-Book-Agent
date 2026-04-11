"""Content module ORM models."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ARRAY, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base

content_type_enum = Enum(
    "image_text",
    "video",
    "moment",
    name="content_type_enum",
)

content_risk_status_enum = Enum(
    "pending",
    "passed",
    "failed",
    "manual_review",
    name="content_risk_status_enum",
)

content_status_enum = Enum(
    "draft",
    "scheduled",
    "published",
    "failed",
    name="content_status_enum",
)


class ContentDraft(Base):
    """Generated content draft waiting for scheduling or publish."""

    __tablename__ = "content_drafts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    alt_titles: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default="{}",
        nullable=False,
    )
    hashtags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default="{}",
        nullable=False,
    )
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        content_type_enum,
        nullable=False,
        server_default="image_text",
    )
    risk_status: Mapped[str] = mapped_column(
        content_risk_status_enum,
        nullable=False,
        server_default="pending",
    )
    status: Mapped[str] = mapped_column(
        content_status_enum,
        nullable=False,
        server_default="draft",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
