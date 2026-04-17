"""Analytics and audit ORM models."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base

operation_log_status_enum = Enum(
    "success",
    "failed",
    "skipped",
    name="operation_log_status_enum",
)

alert_severity_enum = Enum(
    "info",
    "warning",
    "critical",
    name="alert_severity_enum",
)


class OperationLog(Base):
    """Operation audit log for publish/reply/dm/risk events."""

    __tablename__ = "operation_logs"
    __table_args__ = (
        Index(
            "ix_operation_logs_merchant_operation_created_at",
            "merchant_id",
            "operation_type",
            "created_at",
        ),
        Index(
            "ix_operation_logs_account_operation_created_at",
            "account_id",
            "operation_type",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    module: Mapped[str] = mapped_column(String(32), nullable=False, server_default="E")
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(operation_log_status_enum, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Alert(Base):
    """Merchant-facing alert record."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index(
            "ix_alerts_merchant_account_created_at",
            "merchant_id",
            "account_id",
            "created_at",
        ),
        Index(
            "ix_alerts_merchant_module_created_at",
            "merchant_id",
            "module",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    module: Mapped[str] = mapped_column(String(32), nullable=False, server_default="E")
    severity: Mapped[str] = mapped_column(
        alert_severity_enum,
        nullable=False,
        server_default="warning",
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    resolved_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
