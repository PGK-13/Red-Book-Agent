"""Analytics model compatibility exports.

Risk-related audit tables now live in app.models.risk so the ORM has a single
source of truth for operation_logs and alerts.
"""

from app.models.risk import Alert, OperationLog

__all__ = ["Alert", "OperationLog"]
