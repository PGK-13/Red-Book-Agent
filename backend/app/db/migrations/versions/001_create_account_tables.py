"""create accounts, account_personas, proxy_configs tables

Revision ID: 001_account_tables
Revises:
Create Date: 2026-04-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = "001_account_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum 类型 ──
    access_type_enum = sa.Enum("oauth", "rpa", "browser", name="access_type_enum")
    account_status_enum = sa.Enum(
        "active", "suspended", "auth_expired", "banned", name="account_status_enum"
    )

    # ── accounts 表 ──
    op.create_table(
        "accounts",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("merchant_id", UUID(as_uuid=False), nullable=False),
        sa.Column("xhs_user_id", sa.String(64), nullable=False),
        sa.Column("nickname", sa.String(128), nullable=False),
        sa.Column("access_type", access_type_enum, nullable=False),
        sa.Column("oauth_token_enc", sa.Text, nullable=True),
        sa.Column("cookie_enc", sa.Text, nullable=True),
        sa.Column("cookie_expires_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            account_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_probed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("merchant_id", "xhs_user_id", name="uq_merchant_xhs_user"),
    )
    op.create_index("ix_accounts_merchant_id", "accounts", ["merchant_id"])
    op.create_index("ix_accounts_status", "accounts", ["status"])

    # ── account_personas 表 ──
    op.create_table(
        "account_personas",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("tone", sa.String(64), nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("tags", ARRAY(sa.Text), server_default="{}", nullable=False),
        sa.Column("follower_count", sa.Integer, nullable=True),
        sa.Column("profile_synced_at", TIMESTAMP(timezone=True), nullable=True),
    )

    # ── proxy_configs 表 ──
    op.create_table(
        "proxy_configs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("proxy_url", sa.Text, nullable=False),
        sa.Column("user_agent", sa.Text, nullable=False),
        sa.Column("screen_resolution", sa.String(16), nullable=False),
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default="Asia/Shanghai",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_table("proxy_configs")
    op.drop_table("account_personas")
    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_accounts_merchant_id", table_name="accounts")
    op.drop_table("accounts")
    sa.Enum(name="account_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="access_type_enum").drop(op.get_bind(), checkfirst=True)
