"""Risk control request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

RiskKeywordCategory = Literal[
    "platform_banned",
    "contraband",
    "exaggeration",
    "competitor",
    "custom",
]
RiskMatchMode = Literal["exact", "fuzzy"]
RiskSeverity = Literal["warn", "block"]
RiskScene = Literal[
    "note_publish",
    "comment_reply",
    "dm_send",
    "comment_inbound",
    "dm_inbound",
]
RiskDecision = Literal["passed", "rewrite_required", "blocked", "manual_review"]
RiskModule = Literal["E"]
RiskDetailSchema = Literal["module_e_risk_event.v1"]


class RiskKeywordCreateRequest(BaseModel):
    """Create a merchant-level risk keyword."""

    keyword: str = Field(..., min_length=1, max_length=128)
    category: RiskKeywordCategory
    replacement: str | None = Field(None, max_length=128)
    match_mode: RiskMatchMode = "exact"
    severity: RiskSeverity = "block"
    is_active: bool = True

    @field_validator("keyword", "replacement")
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be blank")
        return stripped


class RiskKeywordUpdateRequest(BaseModel):
    """Update a risk keyword."""

    keyword: str | None = Field(None, min_length=1, max_length=128)
    category: RiskKeywordCategory | None = None
    replacement: str | None = Field(None, max_length=128)
    match_mode: RiskMatchMode | None = None
    severity: RiskSeverity | None = None
    is_active: bool | None = None

    @field_validator("keyword", "replacement")
    @classmethod
    def strip_optional_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be blank")
        return stripped


class RiskKeywordResponse(BaseModel):
    """Risk keyword response payload."""

    id: UUID
    merchant_id: UUID | None = None
    keyword: str
    category: RiskKeywordCategory
    replacement: str | None = None
    match_mode: RiskMatchMode
    severity: RiskSeverity
    is_active: bool
    created_at: datetime


class RiskScanRequest(BaseModel):
    """Manual risk scan request payload."""

    account_id: UUID
    scene: RiskScene
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content cannot be blank")
        return stripped


class RiskHitResponse(BaseModel):
    """Single risk hit in scanned content."""

    keyword: str
    category: RiskKeywordCategory
    start: int = Field(..., ge=0)
    end: int = Field(..., gt=0)
    replacement: str | None = None
    severity: RiskSeverity


class RiskScanResponse(BaseModel):
    """Unified risk scan decision."""

    passed: bool
    decision: RiskDecision
    hits: list[RiskHitResponse] = Field(default_factory=list)
    similarity_score: float | None = Field(None, ge=0.0, le=1.0)
    matched_history_id: UUID | None = None
    retryable: bool = False


class AccountRiskScheduleRequest(BaseModel):
    """Per-account rest-window configuration."""

    rest_windows: list[str] = Field(
        ...,
        description='Examples: ["00:00-08:00", "13:00-14:00"]',
    )

    @field_validator("rest_windows")
    @classmethod
    def validate_rest_windows(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for window in value:
            item = window.strip()
            if not item:
                raise ValueError("rest window cannot be blank")
            if not _is_valid_rest_window(item):
                raise ValueError("rest window must match HH:MM-HH:MM")
            normalized.append(item)
        return normalized


class AccountRiskQuotaResponse(BaseModel):
    """Current account quota usage and rest-window state."""

    account_id: UUID
    comment_reply_used: int = Field(..., ge=0)
    comment_reply_limit: int = Field(..., ge=0)
    dm_send_used: int = Field(..., ge=0)
    dm_send_limit: int = Field(..., ge=0)
    note_publish_used: int = Field(..., ge=0)
    note_publish_limit: int = Field(..., ge=0)
    in_rest_window: bool


class RiskEventResponse(BaseModel):
    """Risk event log item."""

    id: UUID
    merchant_id: UUID
    account_id: UUID
    module: RiskModule
    operation_type: str
    status: str
    risk_decision: RiskDecision
    violations: list[str] = Field(default_factory=list)
    detail_schema: RiskDetailSchema
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


def _is_valid_rest_window(value: str) -> bool:
    parts = value.split("-")
    if len(parts) != 2:
        return False
    start, end = parts
    return _is_valid_hhmm(start) and _is_valid_hhmm(end)


def _is_valid_hhmm(value: str) -> bool:
    parts = value.split(":")
    if len(parts) != 2:
        return False

    hour, minute = parts
    if len(hour) != 2 or len(minute) != 2 or not hour.isdigit() or not minute.isdigit():
        return False

    hour_int = int(hour)
    minute_int = int(minute)
    return 0 <= hour_int <= 23 and 0 <= minute_int <= 59
