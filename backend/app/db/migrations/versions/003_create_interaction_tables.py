"""create interaction tables

Revision ID: 003_interaction_tables
Revises: 002_risk_tables
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = "003_interaction_tables"
down_revision = "002_risk_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ENUM 类型
    reply_status_enum = sa.Enum(
        "pending",
        "replied",
        "manual_review",
        "skipped",
        name="reply_status_enum",
    )
    conversation_mode_enum = sa.Enum(
        "auto",
        "human_takeover",
        "pending",
        name="conversation_mode_enum",
    )
    message_role_enum = sa.Enum(
        "user",
        "assistant",
        name="message_role_enum",
    )
    hitl_source_type_enum = sa.Enum(
        "comment",
        "message",
        name="hitl_source_type_enum",
    )
    hitl_trigger_reason_enum = sa.Enum(
        "low_confidence",
        "complaint",
        "competitor_mention",
        "high_value_bd",
        "strong_negative",
        "captcha_detected",
        name="hitl_trigger_reason_enum",
    )
    hitl_status_enum = sa.Enum(
        "pending",
        "approved",
        "rejected",
        "edited",
        name="hitl_status_enum",
    )

    # ── comments ──────────────────────────────────────────────────────────────
    op.create_table(
        "comments",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xhs_note_id", sa.String(64), nullable=False),
        sa.Column("xhs_comment_id", sa.String(64), unique=True, nullable=False),
        sa.Column("xhs_user_id", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "image_urls",
            ARRAY(sa.Text),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("ocr_result", sa.Text, nullable=True),
        sa.Column("intent", sa.String(32), nullable=True),
        sa.Column("intent_confidence", sa.Float, nullable=True),
        sa.Column("sentiment_score", sa.Float, nullable=True),
        sa.Column(
            "reply_status",
            reply_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "deduplicated",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("detected_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_comments_merchant_status_created",
        "comments",
        ["merchant_id", "reply_status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_comments_account_note_created",
        "comments",
        ["account_id", "xhs_note_id", sa.text("created_at DESC")],
    )

    # ── conversations ───────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xhs_user_id", sa.String(64), nullable=False),
        sa.Column(
            "mode",
            conversation_mode_enum,
            nullable=False,
            server_default=sa.text("'auto'"),
        ),
        sa.Column("user_long_term_memory", sa.JSON, nullable=True),
        sa.Column("online_hours_start", sa.Time, nullable=True),
        sa.Column("online_hours_end", sa.Time, nullable=True),
        sa.Column("last_message_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("account_id", "xhs_user_id", name="uq_account_xhs_user"),
    )
    op.create_index(
        "ix_conversations_merchant_mode_updated",
        "conversations",
        ["merchant_id", "mode", sa.text("last_message_at DESC")],
    )

    # ── messages ─────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("xhs_msg_id", sa.String(64), unique=True, nullable=True),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=False),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("role", message_role_enum, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("intent", sa.String(32), nullable=True),
        sa.Column("intent_confidence", sa.Float, nullable=True),
        sa.Column("sentiment_score", sa.Float, nullable=True),
        sa.Column(
            "sent_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_messages_conversation_sent_at",
        "messages",
        ["conversation_id", sa.text("sent_at DESC")],
    )

    # ── intent_logs ──────────────────────────────────────────────────────────
    op.create_table(
        "intent_logs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column("source_type", hitl_source_type_enum, nullable=False),
        sa.Column("source_id", UUID(as_uuid=False), nullable=False),
        sa.Column("raw_input", sa.Text, nullable=False),
        sa.Column("intent", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("sentiment_score", sa.Float, nullable=False),
        sa.Column("llm_latency_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_intent_logs_merchant_created",
        "intent_logs",
        ["merchant_id", sa.text("created_at DESC")],
    )

    # ── hitl_queue ──────────────────────────────────────────────────────────
    op.create_table(
        "hitl_queue",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=False),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "comment_id",
            UUID(as_uuid=False),
            sa.ForeignKey("comments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trigger_reason", hitl_trigger_reason_enum, nullable=False),
        sa.Column("original_content", sa.Text, nullable=False),
        sa.Column("suggested_reply", sa.Text, nullable=True),
        sa.Column("final_reply", sa.Text, nullable=True),
        sa.Column(
            "status",
            hitl_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_by", UUID(as_uuid=False), nullable=True),
        sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_hitl_queue_merchant_status_created",
        "hitl_queue",
        ["merchant_id", "status", sa.text("created_at DESC")],
    )

    # ── dm_trigger_logs ─────────────────────────────────────────────────────
    op.create_table(
        "dm_trigger_logs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xhs_user_id", sa.String(64), nullable=False),
        sa.Column("xhs_comment_id", sa.String(64), nullable=False),
        sa.Column("intent", sa.String(32), nullable=False),
        sa.Column(
            "triggered_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_dm_trigger_logs_merchant_user_intent_expires",
        "dm_trigger_logs",
        ["merchant_id", "xhs_user_id", "intent", "expires_at"],
    )

    # ── monitored_notes ─────────────────────────────────────────────────────
    op.create_table(
        "monitored_notes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xhs_note_id", sa.String(64), nullable=False),
        sa.Column("note_title", sa.String(256), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "check_interval_seconds",
            sa.Integer,
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column(
            "batch_size",
            sa.Integer,
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column("last_checked_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "last_known_comment_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_seen_comment_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("account_id", "xhs_note_id", name="uq_account_xhs_note"),
    )
    op.create_index(
        "ix_monitored_notes_account_active_checked",
        "monitored_notes",
        ["account_id", "is_active", sa.text("last_checked_at ASC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monitored_notes_account_active_checked",
        table_name="monitored_notes",
    )
    op.drop_table("monitored_notes")

    op.drop_index(
        "ix_dm_trigger_logs_merchant_user_intent_expires",
        table_name="dm_trigger_logs",
    )
    op.drop_table("dm_trigger_logs")

    op.drop_index(
        "ix_hitl_queue_merchant_status_created",
        table_name="hitl_queue",
    )
    op.drop_table("hitl_queue")

    op.drop_index(
        "ix_intent_logs_merchant_created",
        table_name="intent_logs",
    )
    op.drop_table("intent_logs")

    op.drop_index(
        "ix_messages_conversation_sent_at",
        table_name="messages",
    )
    op.drop_table("messages")

    op.drop_index(
        "ix_conversations_merchant_mode_updated",
        table_name="conversations",
    )
    op.drop_table("conversations")

    op.drop_index(
        "ix_comments_account_note_created",
        table_name="comments",
    )
    op.drop_index(
        "ix_comments_merchant_status_created",
        table_name="comments",
    )
    op.drop_table("comments")

    # 清理 enum 类型
    sa.Enum(name="hitl_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="hitl_trigger_reason_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="hitl_source_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="message_role_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="conversation_mode_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reply_status_enum").drop(op.get_bind(), checkfirst=True)
