"""Analytics and audit ORM models.

Note: OperationLog and Alert models are defined in app.models.risk to avoid
duplicate table definitions. This module re-exports them for convenience.
"""

from app.models.risk import Alert, OperationLog  # noqa: F401
