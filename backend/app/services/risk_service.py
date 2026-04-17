"""Risk control service helpers.

Task 3.1 covers keyword configuration management and task 3.2 adds sensitive
keyword scanning.
"""

from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from typing import Literal, TypedDict

from app.core.notifications import send_alert
from app.core.rate_limiter import get_redis
from app.models.account import Account
from app.models.risk import (
    AccountRiskConfig,
    Alert,
    OperationLog,
    ReplyHistory,
    RiskKeyword,
)
from app.schemas.risk import (
    AccountRiskScheduleRequest,
    RiskHitResponse,
    RiskKeywordCreateRequest,
    RiskKeywordUpdateRequest,
    RiskScanResponse,
)
from fastapi import HTTPException, status
from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REPLY_HISTORY_CACHE_SIZE = 100
REPLY_HISTORY_CACHE_TTL_SECONDS = 86400

RiskOperationStatus = Literal["success", "blocked", "rewrite_required", "manual_review"]


class QuotaRule(TypedDict):
    merchant_id: str
    limit: int
    bucket: str
    ttl_seconds: int


async def log_risk_event(
    merchant_id: str,
    account_id: str,
    operation_type: str,
    status: RiskOperationStatus,
    risk_decision: str,
    violations: list[str],
    db: AsyncSession,
    detail: dict | None = None,
    error_code: str | None = None,
    content_snapshot: str | None = None,
    source_record_id: str | None = None,
) -> OperationLog:
    """Persist a risk control operation log entry."""

    payload = {
        "risk_decision": risk_decision,
        "violations": violations,
    }
    if detail:
        payload.update(detail)

    event = OperationLog(
        merchant_id=merchant_id,
        account_id=account_id,
        operation_type=operation_type,
        status=status,
        content_snapshot=content_snapshot,
        risk_reason=_build_risk_reason(
            risk_decision=risk_decision,
            detail=detail,
            error_code=error_code,
        ),
        detail=payload,
        error_code=error_code,
        source_record_id=source_record_id,
    )
    db.add(event)
    await db.flush()
    return event


def _build_risk_reason(
    risk_decision: str,
    detail: dict | None,
    error_code: str | None,
) -> str:
    if error_code:
        return error_code
    if detail is not None and isinstance(detail.get("reason"), str):
        return detail["reason"]
    return risk_decision


def _decision_to_log_status(decision: str) -> RiskOperationStatus:
    if decision == "blocked":
        return "blocked"
    if decision == "rewrite_required":
        return "rewrite_required"
    if decision == "manual_review":
        return "manual_review"
    if decision == "passed":
        return "success"
    raise ValueError(f"Unsupported risk decision for operation log status: {decision}")


async def emit_alert_if_needed(
    merchant_id: str,
    alert_type: str,
    message: str,
    db: AsyncSession,
    account_id: str | None = None,
    severity: str = "warning",
) -> Alert:
    """Persist an alert record and dispatch the notification hook."""

    alert = await _create_alert_record(
        merchant_id=merchant_id,
        account_id=account_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
        db=db,
    )
    await send_alert(
        merchant_id=merchant_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
    )
    return alert


async def _create_alert_record(
    merchant_id: str,
    account_id: str | None,
    alert_type: str,
    message: str,
    severity: str,
    db: AsyncSession,
) -> Alert:
    alert = Alert(
        merchant_id=merchant_id,
        account_id=account_id,
        alert_type=alert_type,
        module="E",
        severity=severity,
        message=message,
    )
    db.add(alert)
    await db.flush()
    return alert


async def list_keywords(
    merchant_id: str,
    category: str | None,
    is_active: bool | None,
    db: AsyncSession,
) -> list[RiskKeyword]:
    """List system-level and merchant-level keywords visible to a merchant."""

    stmt = select(RiskKeyword).where(
        or_(
            RiskKeyword.merchant_id.is_(None),
            RiskKeyword.merchant_id == merchant_id,
        )
    )

    if category is not None:
        stmt = stmt.where(RiskKeyword.category == category)
    if is_active is not None:
        stmt = stmt.where(RiskKeyword.is_active.is_(is_active))

    stmt = stmt.order_by(
        case((RiskKeyword.merchant_id == merchant_id, 0), else_=1),
        RiskKeyword.category.asc(),
        RiskKeyword.keyword.asc(),
        RiskKeyword.created_at.desc(),
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_keyword(
    merchant_id: str,
    data: RiskKeywordCreateRequest,
    db: AsyncSession,
) -> RiskKeyword:
    """Create a merchant-level risk keyword."""

    await _ensure_keyword_unique(
        merchant_id=merchant_id,
        keyword=data.keyword,
        category=data.category,
        db=db,
    )

    keyword = RiskKeyword(
        merchant_id=merchant_id,
        keyword=data.keyword,
        category=data.category,
        replacement=data.replacement,
        match_mode=data.match_mode,
        severity=data.severity,
        is_active=data.is_active,
    )
    db.add(keyword)
    await db.flush()
    return keyword


async def update_keyword(
    merchant_id: str,
    keyword_id: str,
    data: RiskKeywordUpdateRequest,
    db: AsyncSession,
) -> RiskKeyword:
    """Update a merchant-owned risk keyword."""

    keyword = await _get_merchant_keyword(
        merchant_id=merchant_id, keyword_id=keyword_id, db=db
    )

    updates = data.model_dump(exclude_unset=True)
    next_keyword = updates.get("keyword", keyword.keyword)
    next_category = updates.get("category", keyword.category)

    if next_keyword != keyword.keyword or next_category != keyword.category:
        await _ensure_keyword_unique(
            merchant_id=merchant_id,
            keyword=next_keyword,
            category=next_category,
            db=db,
            exclude_keyword_id=keyword_id,
        )

    for field, value in updates.items():
        setattr(keyword, field, value)

    await db.flush()
    return keyword


async def delete_keyword(
    merchant_id: str,
    keyword_id: str,
    db: AsyncSession,
) -> None:
    """Delete a merchant-owned risk keyword."""

    keyword = await _get_merchant_keyword(
        merchant_id=merchant_id, keyword_id=keyword_id, db=db
    )
    await db.delete(keyword)
    await db.flush()


async def _get_merchant_keyword(
    merchant_id: str,
    keyword_id: str,
    db: AsyncSession,
) -> RiskKeyword:
    stmt = select(RiskKeyword).where(
        and_(
            RiskKeyword.id == keyword_id,
            RiskKeyword.merchant_id == merchant_id,
        )
    )
    result = await db.execute(stmt)
    keyword = result.scalar_one_or_none()
    if keyword is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关键词不存在",
        )
    return keyword


async def _ensure_keyword_unique(
    merchant_id: str,
    keyword: str,
    category: str,
    db: AsyncSession,
    exclude_keyword_id: str | None = None,
) -> None:
    stmt = select(RiskKeyword.id).where(
        and_(
            RiskKeyword.merchant_id == merchant_id,
            RiskKeyword.keyword == keyword,
            RiskKeyword.category == category,
        )
    )
    if exclude_keyword_id is not None:
        stmt = stmt.where(RiskKeyword.id != exclude_keyword_id)

    result = await db.execute(stmt)
    duplicate_id = result.scalar_one_or_none()
    if duplicate_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同分类下关键词已存在",
        )


async def scan_sensitive_keywords(
    content: str,
    merchant_id: str,
    db: AsyncSession,
) -> list[RiskHitResponse]:
    """Scan active system and merchant keywords and return hit details."""

    normalized_content = content.strip()
    if not normalized_content:
        return []

    keywords = await _load_active_scan_keywords(merchant_id=merchant_id, db=db)
    hits: list[RiskHitResponse] = []

    for keyword in keywords:
        if keyword.match_mode == "fuzzy":
            matches = _find_fuzzy_matches(normalized_content, keyword.keyword)
        else:
            matches = _find_exact_matches(normalized_content, keyword.keyword)

        for start, end in matches:
            hits.append(
                RiskHitResponse(
                    keyword=keyword.keyword,
                    category=keyword.category,
                    start=start,
                    end=end,
                    replacement=keyword.replacement,
                    severity=keyword.severity,
                )
            )

    hits.sort(key=lambda item: (item.start, item.end, item.keyword))
    return hits


async def _load_active_scan_keywords(
    merchant_id: str,
    db: AsyncSession,
) -> list[RiskKeyword]:
    stmt = (
        select(RiskKeyword)
        .where(
            and_(
                RiskKeyword.is_active.is_(True),
                RiskKeyword.category != "competitor",
                or_(
                    RiskKeyword.merchant_id.is_(None),
                    RiskKeyword.merchant_id == merchant_id,
                ),
            )
        )
        .order_by(
            case((RiskKeyword.merchant_id == merchant_id, 0), else_=1),
            RiskKeyword.created_at.desc(),
        )
    )

    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    deduped: list[RiskKeyword] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row.keyword, row.category, row.match_mode)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _find_exact_matches(content: str, keyword: str) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []
    search_from = 0
    while True:
        start = content.find(keyword, search_from)
        if start == -1:
            break
        end = start + len(keyword)
        matches.append((start, end))
        search_from = start + 1
    return matches


def _find_fuzzy_matches(content: str, keyword: str) -> list[tuple[int, int]]:
    """Match windows within Levenshtein distance <= 1."""

    keyword_length = len(keyword)
    if keyword_length == 0:
        return []

    matches: list[tuple[int, int]] = []
    seen_windows: set[tuple[int, int]] = set()

    for window_length in {keyword_length - 1, keyword_length, keyword_length + 1}:
        if window_length <= 0 or window_length > len(content):
            continue

        for start in range(0, len(content) - window_length + 1):
            end = start + window_length
            candidate = content[start:end]
            if _levenshtein_distance_at_most_one(candidate, keyword):
                window = (start, end)
                if window not in seen_windows:
                    seen_windows.add(window)
                    matches.append(window)

    matches.sort()
    return matches


def _levenshtein_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True

    left_len = len(left)
    right_len = len(right)
    if abs(left_len - right_len) > 1:
        return False

    i = 0
    j = 0
    edits = 0

    while i < left_len and j < right_len:
        if left[i] == right[j]:
            i += 1
            j += 1
            continue

        edits += 1
        if edits > 1:
            return False

        if left_len == right_len:
            i += 1
            j += 1
        elif left_len > right_len:
            i += 1
        else:
            j += 1

    if i < left_len or j < right_len:
        edits += 1

    return edits <= 1


async def scan_input(
    merchant_id: str,
    account_id: str,
    scene: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse:
    """Scan inbound content for observation only without blocking the flow."""

    if scene not in {"comment_inbound", "dm_inbound"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scene must be comment_inbound or dm_inbound",
        )

    await _ensure_account_belongs_to_merchant(
        merchant_id=merchant_id,
        account_id=account_id,
        db=db,
    )

    hits = await scan_sensitive_keywords(
        content=content, merchant_id=merchant_id, db=db
    )
    competitor_hits = await scan_competitor_keywords(
        content=content,
        merchant_id=merchant_id,
        db=db,
    )
    hits.extend(competitor_hits)
    if competitor_hits:
        await _track_competitor_hits(
            merchant_id=merchant_id,
            account_id=account_id,
            hit_count=len(competitor_hits),
            db=db,
        )

    if hits:
        categories = sorted({hit.category for hit in hits})
        logger.warning(
            "Inbound risk hits detected merchant=%s account=%s scene=%s categories=%s keywords=%s",
            merchant_id,
            account_id,
            scene,
            categories,
            [hit.keyword for hit in hits],
        )
        await log_risk_event(
            merchant_id=merchant_id,
            account_id=account_id,
            operation_type=scene,
            status="success",
            risk_decision="passed",
            violations=_extract_hit_keywords(hits),
            detail={"observed_only": True, "categories": categories},
            db=db,
        )
        await send_alert(
            merchant_id=merchant_id,
            alert_type="inbound_risk_hit",
            message=(
                f"账号 {account_id} 在 {scene} 场景检测到入站风险内容，"
                f"命中 {len(hits)} 个关键词"
            ),
            severity="warning",
        )
        await _create_alert_record(
            merchant_id=merchant_id,
            account_id=account_id,
            alert_type="inbound_risk_hit",
            message=f"Account {account_id} detected inbound risk content in {scene}",
            severity="warning",
            db=db,
        )
    else:
        logger.info(
            "Inbound content scanned cleanly merchant=%s account=%s scene=%s",
            merchant_id,
            account_id,
            scene,
        )
        await log_risk_event(
            merchant_id=merchant_id,
            account_id=account_id,
            operation_type=scene,
            status="success",
            risk_decision="passed",
            violations=[],
            detail={"observed_only": True},
            db=db,
        )

    return RiskScanResponse(
        passed=True,
        decision="passed",
        hits=hits,
        retryable=False,
    )


async def scan_output(
    merchant_id: str,
    account_id: str,
    scene: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse:
    """Run the unified outbound risk scan and return a single decision object."""

    if scene not in {"note_publish", "comment_reply", "dm_send"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scene must be note_publish, comment_reply or dm_send",
        )

    await _ensure_account_belongs_to_merchant(
        merchant_id=merchant_id,
        account_id=account_id,
        db=db,
    )

    rest_decision = await _check_rest_window_for_output(
        account_id=account_id, scene=scene, db=db
    )
    if rest_decision is not None:
        await log_risk_event(
            merchant_id=merchant_id,
            account_id=account_id,
            operation_type=scene,
            status="blocked",
            risk_decision=rest_decision.decision,
            violations=[],
            detail={"reason": "rest_window"},
            error_code="rest_window_blocked",
            db=db,
        )
        return rest_decision

    quota_decision = await _check_quota_for_output(
        account_id=account_id, scene=scene, db=db
    )
    if quota_decision is not None:
        await log_risk_event(
            merchant_id=merchant_id,
            account_id=account_id,
            operation_type=scene,
            status="blocked",
            risk_decision=quota_decision.decision,
            violations=[],
            detail={"reason": "quota_exceeded"},
            error_code="quota_exceeded",
            db=db,
        )
        return quota_decision

    hits = await scan_sensitive_keywords(
        content=content, merchant_id=merchant_id, db=db
    )
    keyword_decision = _build_keyword_decision(hits=hits)
    if keyword_decision is not None:
        await log_risk_event(
            merchant_id=merchant_id,
            account_id=account_id,
            operation_type=scene,
            status=_decision_to_log_status(keyword_decision.decision),
            risk_decision=keyword_decision.decision,
            violations=_extract_hit_keywords(hits),
            detail={"reason": "sensitive_keywords"},
            error_code="sensitive_keyword_hit",
            db=db,
        )
        return keyword_decision

    competitor_decision = await _check_competitor_for_output(
        merchant_id=merchant_id,
        account_id=account_id,
        scene=scene,
        content=content,
        db=db,
    )
    if competitor_decision is not None:
        await log_risk_event(
            merchant_id=merchant_id,
            account_id=account_id,
            operation_type=scene,
            status=_decision_to_log_status(competitor_decision.decision),
            risk_decision=competitor_decision.decision,
            violations=_extract_hit_keywords(competitor_decision.hits),
            detail={"reason": "competitor_keywords"},
            error_code="competitor_keyword_hit",
            db=db,
        )
        return competitor_decision

    similarity_decision = await _check_similarity_for_output(
        account_id=account_id,
        scene=scene,
        content=content,
        db=db,
    )
    if similarity_decision is not None:
        await log_risk_event(
            merchant_id=merchant_id,
            account_id=account_id,
            operation_type=scene,
            status=_decision_to_log_status(similarity_decision.decision),
            risk_decision=similarity_decision.decision,
            violations=[],
            detail={
                "reason": "reply_similarity",
                "similarity_score": similarity_decision.similarity_score,
                "matched_history_id": (
                    str(similarity_decision.matched_history_id)
                    if similarity_decision.matched_history_id is not None
                    else None
                ),
            },
            error_code="reply_similarity_hit",
            db=db,
        )
        return similarity_decision

    await log_risk_event(
        merchant_id=merchant_id,
        account_id=account_id,
        operation_type=scene,
        status="success",
        risk_decision="passed",
        violations=[],
        detail={"reason": "passed"},
        db=db,
    )
    return RiskScanResponse(
        passed=True,
        decision="passed",
        hits=[],
        retryable=False,
    )


async def update_account_schedule(
    merchant_id: str,
    account_id: str,
    data: AccountRiskScheduleRequest,
    db: AsyncSession,
) -> AccountRiskConfig:
    """Create or update the per-account rest-window configuration."""

    await _ensure_account_belongs_to_merchant(
        merchant_id=merchant_id,
        account_id=account_id,
        db=db,
    )

    stmt = select(AccountRiskConfig).where(AccountRiskConfig.account_id == account_id)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config is None:
        config = AccountRiskConfig(
            merchant_id=merchant_id,
            account_id=account_id,
            rest_windows=data.rest_windows,
        )
        db.add(config)
    else:
        config.merchant_id = merchant_id
        config.rest_windows = data.rest_windows

    await db.flush()
    await _cache_rest_windows(account_id=account_id, rest_windows=config.rest_windows)
    return config


async def is_in_rest_window(
    account_id: str,
    now: datetime,
    db: AsyncSession,
) -> bool:
    """Check whether the current timestamp falls inside the account rest windows."""

    rest_windows = await _get_rest_windows(account_id=account_id, db=db)
    if not rest_windows:
        return False

    minute_of_day = _to_minute_of_day(now)
    return any(_minute_in_window(minute_of_day, window) for window in rest_windows)


async def _ensure_account_belongs_to_merchant(
    merchant_id: str,
    account_id: str,
    db: AsyncSession,
) -> None:
    stmt = select(Account.id).where(
        and_(
            Account.id == account_id,
            Account.merchant_id == merchant_id,
        )
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在",
        )


async def _check_rest_window_for_output(
    account_id: str,
    scene: str,
    db: AsyncSession,
) -> RiskScanResponse | None:
    in_rest_window = await is_in_rest_window(
        account_id=account_id,
        now=datetime.now(timezone.utc),
        db=db,
    )
    if not in_rest_window:
        return None

    logger.warning("Rest-window block account=%s scene=%s", account_id, scene)
    return RiskScanResponse(
        passed=False,
        decision="blocked",
        hits=[],
        retryable=False,
    )


async def _check_quota_for_output(
    account_id: str,
    scene: str,
    db: AsyncSession,
) -> RiskScanResponse | None:
    allowed = await check_and_reserve_quota(account_id=account_id, action=scene, db=db)
    if allowed:
        return None
    return RiskScanResponse(
        passed=False,
        decision="blocked",
        hits=[],
        retryable=False,
    )


async def _check_competitor_for_output(
    merchant_id: str,
    account_id: str,
    scene: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse | None:
    competitor_hits = await scan_competitor_keywords(
        content=content,
        merchant_id=merchant_id,
        db=db,
    )
    if not competitor_hits:
        logger.debug(
            "Competitor check clean merchant=%s account=%s scene=%s content_length=%s",
            merchant_id,
            account_id,
            scene,
            len(content),
        )
        return None

    await _track_competitor_hits(
        merchant_id,
        account_id,
        len(competitor_hits),
        db,
    )
    logger.info(
        "Competitor hits detected merchant=%s account=%s scene=%s count=%s",
        merchant_id,
        account_id,
        scene,
        len(competitor_hits),
    )
    return RiskScanResponse(
        passed=False,
        decision="rewrite_required",
        hits=competitor_hits,
        retryable=True,
    )


async def _check_similarity_for_output(
    account_id: str,
    scene: str,
    content: str,
    db: AsyncSession,
) -> RiskScanResponse | None:
    if scene not in {"comment_reply", "dm_send"}:
        return None

    similarity_result = await detect_similarity(
        account_id=account_id, candidate=content, db=db
    )
    if similarity_result is None:
        return None
    return RiskScanResponse(
        passed=False,
        decision="rewrite_required",
        hits=[],
        similarity_score=similarity_result["similarity_score"],
        matched_history_id=similarity_result["matched_history_id"],
        retryable=True,
    )


def _build_keyword_decision(hits: list[RiskHitResponse]) -> RiskScanResponse | None:
    if not hits:
        return None

    has_blocking_hit = any(
        hit.severity == "block" and hit.category != "competitor" for hit in hits
    )
    if has_blocking_hit:
        return RiskScanResponse(
            passed=False,
            decision="blocked",
            hits=hits,
            retryable=False,
        )

    return RiskScanResponse(
        passed=False,
        decision="rewrite_required",
        hits=hits,
        retryable=True,
    )


def _extract_hit_keywords(hits: list[RiskHitResponse]) -> list[str]:
    return [hit.keyword for hit in hits]


async def scan_competitor_keywords(
    content: str,
    merchant_id: str,
    db: AsyncSession,
) -> list[RiskHitResponse]:
    """Scan competitor keywords with whole-word exact and edit-distance-1 fuzzy matching."""

    normalized_content = content.strip()
    if not normalized_content:
        return []

    keywords = await _load_competitor_keywords(merchant_id=merchant_id, db=db)
    hits: list[RiskHitResponse] = []

    for keyword in keywords:
        if keyword.match_mode == "fuzzy":
            matches = _find_fuzzy_matches(normalized_content, keyword.keyword)
        else:
            matches = _find_whole_word_matches(normalized_content, keyword.keyword)

        for start, end in matches:
            hits.append(
                RiskHitResponse(
                    keyword=keyword.keyword,
                    category=keyword.category,
                    start=start,
                    end=end,
                    replacement=keyword.replacement,
                    severity=keyword.severity,
                )
            )

    hits.sort(key=lambda item: (item.start, item.end, item.keyword))
    return hits


async def _load_competitor_keywords(
    merchant_id: str,
    db: AsyncSession,
) -> list[RiskKeyword]:
    stmt = (
        select(RiskKeyword)
        .where(
            and_(
                RiskKeyword.is_active.is_(True),
                RiskKeyword.category == "competitor",
                or_(
                    RiskKeyword.merchant_id.is_(None),
                    RiskKeyword.merchant_id == merchant_id,
                ),
            )
        )
        .order_by(
            case((RiskKeyword.merchant_id == merchant_id, 0), else_=1),
            RiskKeyword.created_at.desc(),
        )
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    deduped: list[RiskKeyword] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.keyword, row.match_mode)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _find_whole_word_matches(content: str, keyword: str) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []
    for start, end in _find_exact_matches(content, keyword):
        if _is_whole_word_match(content, start, end):
            matches.append((start, end))
    return matches


def _is_whole_word_match(content: str, start: int, end: int) -> bool:
    left_ok = start == 0 or not content[start - 1].isalnum()
    right_ok = end == len(content) or not content[end].isalnum()
    return left_ok and right_ok


async def _track_competitor_hits(
    merchant_id: str,
    account_id: str,
    hit_count: int,
    db: AsyncSession,
) -> int:
    threshold = await _get_competitor_alert_threshold(account_id=account_id, db=db)
    redis = get_redis()
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    key = f"risk:competitor_hits:{account_id}:{bucket}"
    total = await redis.incrby(key, hit_count)
    if total == hit_count:
        await redis.expire(key, 3600)

    if total > threshold:
        await emit_alert_if_needed(
            merchant_id=merchant_id,
            account_id=account_id,
            alert_type="competitor_hits_abnormal",
            message=(
                f"账号 {account_id} 1 小时内竞品命中次数异常升高，"
                f"当前累计 {total} 次"
            ),
            db=db,
            severity="warning",
        )
    return int(total)


async def _get_competitor_alert_threshold(account_id: str, db: AsyncSession) -> int:
    stmt = select(AccountRiskConfig.competitor_alert_threshold_per_hour).where(
        AccountRiskConfig.account_id == account_id
    )
    result = await db.execute(stmt)
    threshold = result.scalar_one_or_none()
    return int(threshold) if threshold is not None else 10


async def check_and_reserve_quota(
    account_id: str,
    action: str,
    db: AsyncSession,
) -> bool:
    """Atomically reserve outbound quota for the given account and action."""

    quota_rule = await _get_quota_rule(account_id=account_id, action=action, db=db)
    redis = get_redis()
    key = _build_quota_key(
        account_id=account_id, action=action, bucket=quota_rule["bucket"]
    )

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, quota_rule["ttl_seconds"])

    if count <= quota_rule["limit"]:
        logger.info(
            "Quota reserved account=%s action=%s count=%s limit=%s",
            account_id,
            action,
            count,
            quota_rule["limit"],
        )
        return True

    await emit_alert_if_needed(
        merchant_id=quota_rule["merchant_id"],
        account_id=account_id,
        alert_type="risk_quota_exceeded",
        message=(
            f"账号 {account_id} 的 {action} 频率已超过阈值 "
            f"({count}/{quota_rule['limit']})，自动操作已阻断"
        ),
        db=db,
        severity="warning",
    )
    logger.warning(
        "Quota exceeded account=%s action=%s count=%s limit=%s",
        account_id,
        action,
        count,
        quota_rule["limit"],
    )
    return False


async def _get_quota_rule(
    account_id: str,
    action: str,
    db: AsyncSession,
) -> QuotaRule:
    if action not in {"comment_reply", "dm_send", "note_publish"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be comment_reply, dm_send or note_publish",
        )

    stmt = (
        select(Account, AccountRiskConfig)
        .outerjoin(AccountRiskConfig, AccountRiskConfig.account_id == Account.id)
        .where(Account.id == account_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在",
        )

    account, config = row
    now = datetime.now(timezone.utc)

    if action == "comment_reply":
        return {
            "merchant_id": account.merchant_id,
            "limit": (
                config.comment_reply_limit_per_hour if config is not None else 20
            ),
            "bucket": now.strftime("%Y%m%d%H"),
            "ttl_seconds": 3600,
        }
    if action == "dm_send":
        return {
            "merchant_id": account.merchant_id,
            "limit": (config.dm_send_limit_per_hour if config is not None else 50),
            "bucket": now.strftime("%Y%m%d%H"),
            "ttl_seconds": 3600,
        }
    return {
        "merchant_id": account.merchant_id,
        "limit": (config.note_publish_limit_per_day if config is not None else 3),
        "bucket": now.strftime("%Y%m%d"),
        "ttl_seconds": 86400,
    }


def _build_quota_key(account_id: str, action: str, bucket: str) -> str:
    return f"risk:quota:{account_id}:{action}:{bucket}"


async def _get_rest_windows(account_id: str, db: AsyncSession) -> list[str]:
    redis = get_redis()
    cache_key = _build_rest_cache_key(account_id)
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    stmt = select(AccountRiskConfig.rest_windows).where(
        AccountRiskConfig.account_id == account_id
    )
    result = await db.execute(stmt)
    rest_windows = result.scalar_one_or_none() or []
    await _cache_rest_windows(account_id=account_id, rest_windows=rest_windows)
    return list(rest_windows)


async def _cache_rest_windows(account_id: str, rest_windows: list[str]) -> None:
    redis = get_redis()
    await redis.setex(
        _build_rest_cache_key(account_id),
        86400,
        json.dumps(rest_windows),
    )


def _build_rest_cache_key(account_id: str) -> str:
    return f"risk:rest:{account_id}"


def _to_minute_of_day(now: datetime) -> int:
    return now.hour * 60 + now.minute


def _minute_in_window(minute_of_day: int, window: str) -> bool:
    """Check whether a minute-of-day falls within a configured time window.

    Window format is "HH:MM-HH:MM". When start < end it is a normal same-day
    window, when start > end it spans across midnight, and when start == end it
    represents an all-day window.
    """

    start_text, end_text = window.split("-")
    start = _hhmm_to_minute(start_text)
    end = _hhmm_to_minute(end_text)

    if start == end:
        return True
    if start < end:
        return start <= minute_of_day < end
    return minute_of_day >= start or minute_of_day < end


def _hhmm_to_minute(value: str) -> int:
    hour_text, minute_text = value.split(":")
    return int(hour_text) * 60 + int(minute_text)


def inject_variants(content: str) -> str:
    """Inject small, explainable text variants to reduce verbatim repetition."""

    updated = content.strip()
    if not updated:
        return updated

    replacements = {
        "您好": "你好",
        "谢谢": "感谢",
        "可以": "能够",
        "马上": "尽快",
        "联系": "沟通",
        "安排": "处理",
    }
    for source, target in replacements.items():
        if source in updated:
            updated = updated.replace(source, target, 1)
            break

    segments = [
        segment.strip()
        for segment in re.split(r"[，,。.!！？?]", updated)
        if segment.strip()
    ]
    if len(segments) >= 2:
        updated = "，".join([segments[1], segments[0], *segments[2:]])

    if updated[-1] not in "。.!！？?~":
        updated = f"{updated}呢"

    return updated


async def apply_humanized_delay(account_id: str, action: str) -> float:
    """Return a humanized delay hint for upstream executors to consume."""

    if action not in {"comment_reply", "dm_send", "note_publish"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be comment_reply, dm_send or note_publish",
        )

    delay_seconds = round(random.uniform(3.0, 15.0), 2)
    logger.info(
        "Generated humanized delay account=%s action=%s delay=%.2fs",
        account_id,
        action,
        delay_seconds,
    )
    return delay_seconds


async def detect_similarity(
    account_id: str,
    candidate: str,
    db: AsyncSession,
) -> dict[str, str | float] | None:
    """Compare a candidate reply against the latest 100 reply histories."""

    normalized_candidate = _normalize_similarity_text(candidate)
    if not normalized_candidate:
        return None

    threshold = await _get_similarity_threshold(account_id=account_id, db=db)
    histories = await _load_recent_reply_history_summaries(account_id=account_id, db=db)

    best_score = 0.0
    best_history: dict[str, str] | None = None
    for history in histories:
        score = _similarity_score(
            normalized_candidate,
            history["normalized_content"],
        )
        if score > best_score:
            best_score = score
            best_history = history

    if best_history is None or best_score < threshold:
        return None

    logger.info(
        "Similarity detected account=%s history_id=%s score=%.4f threshold=%.2f",
        account_id,
        best_history["id"],
        best_score,
        threshold,
    )
    return {
        "similarity_score": round(best_score, 4),
        "matched_history_id": best_history["id"],
        "rewrite_suggestion": inject_variants(candidate),
    }


async def persist_reply_history(
    account_id: str,
    content: str,
    source_type: str,
    source_record_id: str | None,
    db: AsyncSession,
) -> ReplyHistory:
    """Persist full reply history to PostgreSQL and cache the latest summaries in Redis."""

    history = ReplyHistory(
        account_id=account_id,
        content=content,
        normalized_content=_normalize_similarity_text(content),
        similarity_hash=_build_similarity_hash(content),
        source_type=source_type,
        source_record_id=source_record_id,
    )
    db.add(history)
    await db.flush()

    await _push_reply_history_summary_to_cache(history)
    return history


async def _get_similarity_threshold(account_id: str, db: AsyncSession) -> float:
    stmt = select(AccountRiskConfig.dedup_similarity_threshold).where(
        AccountRiskConfig.account_id == account_id
    )
    result = await db.execute(stmt)
    threshold = result.scalar_one_or_none()
    return float(threshold) if threshold is not None else 0.85


def _normalize_similarity_text(content: str) -> str:
    lowered = content.strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[，,。.!！？?~]+", "", lowered)
    return lowered


def _similarity_score(left: str, right: str) -> float:
    normalized_right = _normalize_similarity_text(right)
    if not left or not normalized_right:
        return 0.0

    sequence_score = SequenceMatcher(None, left, normalized_right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(normalized_right.split())
    if left_tokens and right_tokens:
        jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    else:
        jaccard = 0.0
    return max(sequence_score, jaccard)


async def _load_recent_reply_history_summaries(
    account_id: str,
    db: AsyncSession,
) -> list[dict[str, str]]:
    cache_key = _build_reply_history_cache_key(account_id)
    try:
        redis = get_redis()
        cached_items = await redis.lrange(cache_key, 0, REPLY_HISTORY_CACHE_SIZE - 1)
        if cached_items:
            return [json.loads(item) for item in cached_items]
    except Exception:
        logger.warning(
            "Failed to read reply history cache account=%s", account_id, exc_info=True
        )

    stmt = (
        select(ReplyHistory)
        .where(ReplyHistory.account_id == account_id)
        .order_by(ReplyHistory.created_at.desc())
        .limit(REPLY_HISTORY_CACHE_SIZE)
    )
    result = await db.execute(stmt)
    histories = list(result.scalars().all())
    summaries = [_reply_history_to_summary(history) for history in histories]
    if summaries:
        await _replace_reply_history_cache(account_id=account_id, summaries=summaries)
    return summaries


async def _push_reply_history_summary_to_cache(history: ReplyHistory) -> None:
    try:
        redis = get_redis()
        cache_key = _build_reply_history_cache_key(history.account_id)
        await redis.lpush(cache_key, json.dumps(_reply_history_to_summary(history)))
        await redis.ltrim(cache_key, 0, REPLY_HISTORY_CACHE_SIZE - 1)
        await redis.expire(cache_key, REPLY_HISTORY_CACHE_TTL_SECONDS)
    except Exception:
        logger.warning(
            "Failed to update reply history cache account=%s history_id=%s",
            history.account_id,
            history.id,
            exc_info=True,
        )


async def _replace_reply_history_cache(
    account_id: str, summaries: list[dict[str, str]]
) -> None:
    try:
        redis = get_redis()
        cache_key = _build_reply_history_cache_key(account_id)
        await redis.delete(cache_key)
        if summaries:
            await redis.rpush(cache_key, *[json.dumps(item) for item in summaries])
            await redis.expire(cache_key, REPLY_HISTORY_CACHE_TTL_SECONDS)
    except Exception:
        logger.warning(
            "Failed to rebuild reply history cache account=%s",
            account_id,
            exc_info=True,
        )


def _reply_history_to_summary(history: ReplyHistory) -> dict[str, str]:
    return {
        "id": history.id,
        "normalized_content": history.normalized_content,
        "similarity_hash": history.similarity_hash or "",
    }


def _build_reply_history_cache_key(account_id: str) -> str:
    return f"risk:reply_history:{account_id}"


def _build_similarity_hash(content: str) -> str | None:
    normalized = _normalize_similarity_text(content)
    if not normalized:
        return None
    return sha256(normalized.encode("utf-8")).hexdigest()


async def scan(content: str, merchant_id: str, db: AsyncSession) -> dict:
    """
    Execute risk scanning before outbound content is published.

    Task 3.2 now covers only sensitive keyword scanning. Other checks stay for
    later tasks.
    """
    hits = await scan_sensitive_keywords(
        content=content, merchant_id=merchant_id, db=db
    )
    return {
        "passed": not hits,
        "violations": [hit.keyword for hit in hits],
    }
