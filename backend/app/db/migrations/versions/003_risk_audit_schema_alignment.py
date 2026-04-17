"""backfill risk audit schema alignment

Revision ID: 003_risk_audit_schema_alignment
Revises: 002_risk_tables
Create Date: 2026-04-17
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "003_risk_audit_schema_alignment"
down_revision = "002_risk_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill columns for databases that already applied the old 002 revision."""

    op.execute(
        """
        ALTER TABLE operation_logs
        ADD COLUMN IF NOT EXISTS detail JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE operation_logs
        ADD COLUMN IF NOT EXISTS error_code VARCHAR(32)
        """
    )
    op.execute(
        """
        ALTER TABLE alerts
        ADD COLUMN IF NOT EXISTS alert_type VARCHAR(64) NOT NULL DEFAULT 'legacy'
        """
    )


def downgrade() -> None:
    """Keep schema intact because 002 now defines the aligned columns."""

    pass
