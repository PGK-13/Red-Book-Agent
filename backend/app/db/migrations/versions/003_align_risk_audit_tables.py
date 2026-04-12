"""align risk audit tables with runtime analytics models

Revision ID: 003_align_risk_audit_tables
Revises: 002_risk_tables
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_align_risk_audit_tables"
down_revision = "002_risk_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    operation_log_status_enum = sa.Enum(
        "success",
        "failed",
        "skipped",
        name="operation_log_status_enum",
    )
    operation_log_status_enum.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("operation_logs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "detail",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            )
        )
        batch_op.add_column(sa.Column("error_code", sa.String(length=32), nullable=True))

    op.execute(
        """
        UPDATE operation_logs
        SET detail = jsonb_strip_nulls(
            jsonb_build_object(
                'migrated_from_legacy', true,
                'content_snapshot', content_snapshot,
                'risk_reason', risk_reason,
                'source_record_id', source_record_id
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE operation_logs
        ALTER COLUMN operation_type TYPE VARCHAR(64)
        USING operation_type::text
        """
    )
    op.execute(
        """
        ALTER TABLE operation_logs
        ALTER COLUMN status TYPE operation_log_status_enum
        USING (
            CASE status::text
                WHEN 'success' THEN 'success'
                WHEN 'blocked' THEN 'failed'
                WHEN 'rewrite_required' THEN 'skipped'
                WHEN 'manual_review' THEN 'skipped'
            END
        )::operation_log_status_enum
        """
    )
    op.alter_column("operation_logs", "detail", server_default=None, nullable=False)
    op.drop_index("ix_operation_logs_account_type_created_at", table_name="operation_logs")
    with op.batch_alter_table("operation_logs") as batch_op:
        batch_op.drop_column("merchant_id")
        batch_op.drop_column("content_snapshot")
        batch_op.drop_column("risk_reason")
        batch_op.drop_column("source_record_id")
    op.create_index(
        "ix_operation_logs_account_operation_created_at",
        "operation_logs",
        ["account_id", "operation_type", "created_at"],
        unique=False,
    )

    with op.batch_alter_table("alerts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "alert_type",
                sa.String(length=64),
                nullable=True,
                server_default="legacy_risk_alert",
            )
        )
        batch_op.add_column(
            sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("resolved_by", postgresql.UUID(as_uuid=False), nullable=True))
        batch_op.add_column(sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE alerts
        SET alert_type = COALESCE(NULLIF(module, ''), 'legacy_risk_alert')
        """
    )
    op.alter_column("alerts", "alert_type", server_default=None, nullable=False)
    op.alter_column("alerts", "module", type_=sa.String(length=32), server_default="E")
    op.alter_column("alerts", "severity", server_default="warning")
    op.drop_index("ix_alerts_merchant_module_created_at", table_name="alerts")
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.drop_constraint("alerts_account_id_fkey", type_="foreignkey")
        batch_op.drop_column("account_id")
    op.create_index("ix_alerts_merchant_id", "alerts", ["merchant_id"], unique=False)
    op.create_index(
        "ix_alerts_merchant_module_created_at",
        "alerts",
        ["merchant_id", "module", "created_at"],
        unique=False,
    )

    sa.Enum(name="operation_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="operation_type_enum").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    operation_type_enum = sa.Enum(
        "note_publish",
        "comment_reply",
        "dm_send",
        "comment_inbound",
        "dm_inbound",
        name="operation_type_enum",
    )
    operation_status_enum = sa.Enum(
        "success",
        "blocked",
        "rewrite_required",
        "manual_review",
        name="operation_status_enum",
    )
    operation_type_enum.create(op.get_bind(), checkfirst=True)
    operation_status_enum.create(op.get_bind(), checkfirst=True)

    op.drop_index("ix_alerts_merchant_id", table_name="alerts")
    op.drop_index("ix_alerts_merchant_module_created_at", table_name="alerts")
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "account_id",
                postgresql.UUID(as_uuid=False),
                nullable=True,
            )
        )
    op.create_foreign_key(
        "alerts_account_id_fkey",
        "alerts",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("resolved_by")
        batch_op.drop_column("is_resolved")
        batch_op.drop_column("alert_type")
    op.alter_column("alerts", "module", type_=sa.String(length=64), server_default=None)
    op.alter_column("alerts", "severity", server_default=None)
    op.create_index(
        "ix_alerts_merchant_module_created_at",
        "alerts",
        ["merchant_id", "module", sa.text("created_at DESC")],
        unique=False,
    )

    op.drop_index("ix_operation_logs_account_operation_created_at", table_name="operation_logs")
    with op.batch_alter_table("operation_logs") as batch_op:
        batch_op.add_column(
            sa.Column("merchant_id", postgresql.UUID(as_uuid=False), nullable=False)
        )
        batch_op.add_column(sa.Column("content_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("risk_reason", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("source_record_id", postgresql.UUID(as_uuid=False), nullable=True)
        )
    op.execute(
        """
        ALTER TABLE operation_logs
        ALTER COLUMN operation_type TYPE operation_type_enum
        USING operation_type::operation_type_enum
        """
    )
    op.execute(
        """
        ALTER TABLE operation_logs
        ALTER COLUMN status TYPE operation_status_enum
        USING (
            CASE status::text
                WHEN 'success' THEN 'success'
                WHEN 'failed' THEN 'blocked'
                WHEN 'skipped' THEN 'rewrite_required'
            END
        )::operation_status_enum
        """
    )
    with op.batch_alter_table("operation_logs") as batch_op:
        batch_op.drop_column("error_code")
        batch_op.drop_column("detail")
    op.create_index(
        "ix_operation_logs_account_type_created_at",
        "operation_logs",
        ["account_id", "operation_type", sa.text("created_at DESC")],
        unique=False,
    )

    sa.Enum(name="operation_log_status_enum").drop(op.get_bind(), checkfirst=True)
