"""create risk tables

Revision ID: 002_risk_tables
Revises: 001_account_tables
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = "002_risk_tables"
down_revision = "001_account_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    risk_keyword_category_enum = sa.Enum(
        "platform_banned",
        "contraband",
        "exaggeration",
        "competitor",
        "custom",
        name="risk_keyword_category_enum",
    )
    risk_match_mode_enum = sa.Enum(
        "exact",
        "fuzzy",
        name="risk_match_mode_enum",
    )
    risk_severity_enum = sa.Enum(
        "warn",
        "block",
        name="risk_severity_enum",
    )
    reply_history_source_type_enum = sa.Enum(
        "comment_reply",
        "dm_send",
        name="reply_history_source_type_enum",
    )
<<<<<<< HEAD
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
    alert_severity_enum = sa.Enum(
        "info",
        "warning",
        "critical",
        name="alert_severity_enum",
    )
=======
>>>>>>> fd63b6f388b7e6e9a0038aae838b134cae665a38

    op.create_table(
        "risk_keywords",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=True),
        sa.Column("keyword", sa.String(128), nullable=False),
        sa.Column("category", risk_keyword_category_enum, nullable=False),
        sa.Column("replacement", sa.String(128), nullable=True),
        sa.Column(
            "match_mode",
            risk_match_mode_enum,
            nullable=False,
            server_default="exact",
        ),
        sa.Column(
            "severity",
            risk_severity_enum,
            nullable=False,
            server_default="block",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "merchant_id",
            "keyword",
            "category",
            name="uq_risk_keyword_scope",
        ),
    )
    op.create_index("ix_risk_keywords_merchant_id", "risk_keywords", ["merchant_id"])
    op.create_index(
        "ix_risk_keywords_merchant_category_active",
        "risk_keywords",
        ["merchant_id", "category", "is_active"],
    )

    op.create_table(
        "account_risk_configs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
<<<<<<< HEAD
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
=======
>>>>>>> fd63b6f388b7e6e9a0038aae838b134cae665a38
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("rest_windows", ARRAY(sa.Text), server_default="{}", nullable=False),
        sa.Column(
            "comment_reply_limit_per_hour",
            sa.Integer,
            nullable=False,
            server_default="20",
        ),
        sa.Column(
            "dm_send_limit_per_hour",
            sa.Integer,
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "note_publish_limit_per_day",
            sa.Integer,
            nullable=False,
            server_default="3",
        ),
        sa.Column(
            "dedup_similarity_threshold",
            sa.Float,
            nullable=False,
            server_default="0.85",
        ),
        sa.Column(
            "competitor_alert_threshold_per_hour",
            sa.Integer,
            nullable=False,
            server_default="10",
        ),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
<<<<<<< HEAD
    op.create_index(
        "ix_account_risk_configs_merchant_id",
        "account_risk_configs",
        ["merchant_id"],
    )
=======
>>>>>>> fd63b6f388b7e6e9a0038aae838b134cae665a38

    op.create_table(
        "reply_histories",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("normalized_content", sa.Text, nullable=False),
        sa.Column("similarity_hash", sa.String(64), nullable=True),
        sa.Column("source_type", reply_history_source_type_enum, nullable=False),
        sa.Column("source_record_id", UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_reply_histories_account_id",
        "reply_histories",
        ["account_id"],
    )
    op.create_index(
        "ix_reply_histories_created_at",
        "reply_histories",
        ["created_at"],
    )
    op.create_index(
        "ix_reply_histories_account_created_at",
        "reply_histories",
<<<<<<< HEAD
        ["account_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "operation_logs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_type", operation_type_enum, nullable=False),
        sa.Column("status", operation_status_enum, nullable=False),
        sa.Column("content_snapshot", sa.Text, nullable=True),
        sa.Column("risk_reason", sa.Text, nullable=True),
        sa.Column("source_record_id", UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_operation_logs_account_type_created_at",
        "operation_logs",
        ["account_id", "operation_type", sa.text("created_at DESC")],
    )

    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("severity", alert_severity_enum, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_alerts_merchant_module_created_at",
        "alerts",
        ["merchant_id", "module", sa.text("created_at DESC")],
=======
        ["account_id", "created_at"],
>>>>>>> fd63b6f388b7e6e9a0038aae838b134cae665a38
    )


def downgrade() -> None:
    op.drop_index(
<<<<<<< HEAD
        "ix_alerts_merchant_module_created_at",
        table_name="alerts",
    )
    op.drop_table("alerts")

    op.drop_index(
        "ix_operation_logs_account_type_created_at",
        table_name="operation_logs",
    )
    op.drop_table("operation_logs")

    op.drop_index(
=======
>>>>>>> fd63b6f388b7e6e9a0038aae838b134cae665a38
        "ix_reply_histories_account_created_at",
        table_name="reply_histories",
    )
    op.drop_index("ix_reply_histories_created_at", table_name="reply_histories")
    op.drop_index("ix_reply_histories_account_id", table_name="reply_histories")
    op.drop_table("reply_histories")

<<<<<<< HEAD
    op.drop_index(
        "ix_account_risk_configs_merchant_id",
        table_name="account_risk_configs",
    )
=======
>>>>>>> fd63b6f388b7e6e9a0038aae838b134cae665a38
    op.drop_table("account_risk_configs")

    op.drop_index(
        "ix_risk_keywords_merchant_category_active",
        table_name="risk_keywords",
    )
    op.drop_index("ix_risk_keywords_merchant_id", table_name="risk_keywords")
    op.drop_table("risk_keywords")

    sa.Enum(name="reply_history_source_type_enum").drop(
        op.get_bind(), checkfirst=True
    )
<<<<<<< HEAD
    sa.Enum(name="alert_severity_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="operation_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="operation_type_enum").drop(op.get_bind(), checkfirst=True)
=======
>>>>>>> fd63b6f388b7e6e9a0038aae838b134cae665a38
    sa.Enum(name="risk_severity_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="risk_match_mode_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="risk_keyword_category_enum").drop(op.get_bind(), checkfirst=True)
