"""add phase2 risk contract columns and indexes

Revision ID: 004_phase2_risk_contract
Revises: 003_align_risk_audit_tables
Create Date: 2026-04-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "004_phase2_risk_contract"
down_revision = "003_align_risk_audit_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "operation_logs",
        sa.Column("merchant_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "operation_logs",
        sa.Column("module", sa.String(length=32), nullable=False, server_default="E"),
    )

    op.execute(
        """
        UPDATE operation_logs AS logs
        SET merchant_id = accounts.merchant_id
        FROM accounts
        WHERE logs.account_id = accounts.id
        """
    )
    op.alter_column("operation_logs", "merchant_id", nullable=False)
    op.create_index(
        "ix_operation_logs_merchant_id",
        "operation_logs",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        "ix_operation_logs_merchant_operation_created_at",
        "operation_logs",
        ["merchant_id", "operation_type", "created_at"],
        unique=False,
    )

    op.add_column(
        "alerts",
        sa.Column("account_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "alerts_account_id_fkey",
        "alerts",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_alerts_account_id", "alerts", ["account_id"], unique=False)
    op.create_index(
        "ix_alerts_merchant_account_created_at",
        "alerts",
        ["merchant_id", "account_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_merchant_account_created_at", table_name="alerts")
    op.drop_index("ix_alerts_account_id", table_name="alerts")
    op.drop_constraint("alerts_account_id_fkey", "alerts", type_="foreignkey")
    op.drop_column("alerts", "account_id")

    op.drop_index(
        "ix_operation_logs_merchant_operation_created_at",
        table_name="operation_logs",
    )
    op.drop_index("ix_operation_logs_merchant_id", table_name="operation_logs")
    op.drop_column("operation_logs", "module")
    op.drop_column("operation_logs", "merchant_id")
