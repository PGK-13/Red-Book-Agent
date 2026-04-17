"""create content drafts table

Revision ID: 005_create_content_drafts
Revises: 004_phase2_risk_contract
Create Date: 2026-04-12 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID


revision = "005_create_content_drafts"
down_revision = "004_phase2_risk_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    content_type_enum = sa.Enum(
        "image_text",
        "video",
        "moment",
        name="content_type_enum",
    )
    content_risk_status_enum = sa.Enum(
        "pending",
        "passed",
        "failed",
        "manual_review",
        name="content_risk_status_enum",
    )
    content_status_enum = sa.Enum(
        "draft",
        "scheduled",
        "published",
        "failed",
        name="content_status_enum",
    )

    op.create_table(
        "content_drafts",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("alt_titles", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("hashtags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column(
            "content_type",
            content_type_enum,
            nullable=False,
            server_default="image_text",
        ),
        sa.Column(
            "risk_status",
            content_risk_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "status",
            content_status_enum,
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_content_drafts_account_id", "content_drafts", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_content_drafts_account_id", table_name="content_drafts")
    op.drop_table("content_drafts")

    sa.Enum(name="content_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="content_risk_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="content_type_enum").drop(op.get_bind(), checkfirst=True)
