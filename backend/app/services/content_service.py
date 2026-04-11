"""Content generation helpers with outbound risk integration."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.content import ContentDraft
from app.schemas.risk import RiskScanResponse
from app.services import risk_service

MAX_DRAFT_RISK_REWRITE_ATTEMPTS = 3


@dataclass(slots=True)
class DraftRiskReviewResult:
    """Result of reviewing a content draft through outbound risk control."""

    draft: ContentDraft
    decision: RiskScanResponse
    attempts_used: int


@dataclass(frozen=True, slots=True)
class _DraftContentSnapshot:
    title: str
    body: str
    alt_titles: tuple[str, ...]
    hashtags: tuple[str, ...]


async def review_draft_outbound_risk(
    merchant_id: str,
    draft_id: str,
    db: AsyncSession,
    max_rewrite_attempts: int = MAX_DRAFT_RISK_REWRITE_ATTEMPTS,
) -> DraftRiskReviewResult:
    """Scan a draft before publish and retry local rewrites when allowed."""

    draft = await _get_draft_for_merchant(
        merchant_id=merchant_id,
        draft_id=draft_id,
        db=db,
    )

    attempts_used = 0
    original_snapshot = _snapshot_draft_content(draft)
    current_decision = await _scan_draft_outbound(merchant_id=merchant_id, draft=draft, db=db)

    while (
        current_decision.decision == "rewrite_required"
        and attempts_used < max_rewrite_attempts
    ):
        attempts_used += 1
        _rewrite_draft_locally(draft, current_decision)
        current_decision = await _scan_draft_outbound(
            merchant_id=merchant_id,
            draft=draft,
            db=db,
        )

    if current_decision.decision == "passed":
        draft.risk_status = "passed"
    elif current_decision.decision == "blocked":
        draft.risk_status = "failed"
    elif current_decision.decision == "rewrite_required":
        _restore_draft_content(draft, original_snapshot)
        draft.risk_status = "manual_review"
        current_decision = current_decision.model_copy(
            update={"decision": "manual_review", "retryable": False}
        )
    else:
        _restore_draft_content(draft, original_snapshot)
        draft.risk_status = "manual_review"

    await db.flush()
    return DraftRiskReviewResult(
        draft=draft,
        decision=current_decision,
        attempts_used=attempts_used,
    )


async def _get_draft_for_merchant(
    merchant_id: str,
    draft_id: str,
    db: AsyncSession,
) -> ContentDraft:
    stmt = (
        select(ContentDraft)
        .join(Account, ContentDraft.account_id == Account.id)
        .where(
            and_(
                ContentDraft.id == draft_id,
                Account.merchant_id == merchant_id,
            )
        )
    )
    result = await db.execute(stmt)
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        )
    return draft


async def _scan_draft_outbound(
    merchant_id: str,
    draft: ContentDraft,
    db: AsyncSession,
) -> RiskScanResponse:
    return await risk_service.scan_output(
        merchant_id=merchant_id,
        account_id=draft.account_id,
        scene="note_publish",
        content=_compose_draft_scan_content(draft),
        db=db,
    )


def _compose_draft_scan_content(draft: ContentDraft) -> str:
    parts = [draft.title.strip(), draft.body.strip()]
    if draft.alt_titles:
        parts.extend(title.strip() for title in draft.alt_titles if title.strip())
    if draft.hashtags:
        parts.append(" ".join(tag.strip() for tag in draft.hashtags if tag.strip()))
    return "\n".join(part for part in parts if part)


def _rewrite_draft_locally(draft: ContentDraft, decision: RiskScanResponse) -> None:
    """Temporary local rewrite fallback until the content agent owns this step."""

    rewritten_title = draft.title
    rewritten_body = draft.body
    rewritten_alt_titles = list(draft.alt_titles or [])
    rewritten_hashtags = list(draft.hashtags or [])

    for hit in decision.hits:
        replacement = (hit.replacement or "").strip()
        if replacement:
            rewritten_title = rewritten_title.replace(hit.keyword, replacement)
            rewritten_body = rewritten_body.replace(hit.keyword, replacement)
            rewritten_alt_titles = [
                title.replace(hit.keyword, replacement)
                for title in rewritten_alt_titles
            ]
            rewritten_hashtags = [
                tag.replace(hit.keyword, replacement)
                for tag in rewritten_hashtags
            ]
        else:
            rewritten_title = _remove_keyword_occurrence(rewritten_title, hit.keyword)
            rewritten_body = _remove_keyword_occurrence(rewritten_body, hit.keyword)
            rewritten_alt_titles = [
                _remove_keyword_occurrence(title, hit.keyword)
                for title in rewritten_alt_titles
            ]
            rewritten_hashtags = [
                _remove_keyword_occurrence(tag, hit.keyword)
                for tag in rewritten_hashtags
            ]
            rewritten_title = rewritten_title.strip()
            rewritten_body = rewritten_body.strip()

    if decision.similarity_score is not None:
        rewritten_title, rewritten_body, rewritten_alt_titles, rewritten_hashtags = (
            _request_content_agent_rewrite(
                draft=draft,
                rewritten_title=rewritten_title,
                rewritten_body=rewritten_body,
                rewritten_alt_titles=rewritten_alt_titles,
                rewritten_hashtags=rewritten_hashtags,
                decision=decision,
            )
        )

    draft.title = rewritten_title.strip() or draft.title
    draft.body = rewritten_body.strip() or draft.body
    draft.alt_titles = [title for title in rewritten_alt_titles if title.strip()]
    draft.hashtags = [tag for tag in rewritten_hashtags if tag.strip()]


def _snapshot_draft_content(draft: ContentDraft) -> _DraftContentSnapshot:
    return _DraftContentSnapshot(
        title=draft.title,
        body=draft.body,
        alt_titles=tuple(draft.alt_titles or []),
        hashtags=tuple(draft.hashtags or []),
    )


def _restore_draft_content(draft: ContentDraft, snapshot: _DraftContentSnapshot) -> None:
    draft.title = snapshot.title
    draft.body = snapshot.body
    draft.alt_titles = list(snapshot.alt_titles)
    draft.hashtags = list(snapshot.hashtags)


def _request_content_agent_rewrite(
    draft: ContentDraft,
    rewritten_title: str,
    rewritten_body: str,
    rewritten_alt_titles: list[str],
    rewritten_hashtags: list[str],
    decision: RiskScanResponse,
) -> tuple[str, str, list[str], list[str]]:
    # TODO: Replace this placeholder with a real content-agent rewrite call once
    # module C exposes a dedicated paragraph/title rewrite capability.
    return rewritten_title, rewritten_body, rewritten_alt_titles, rewritten_hashtags


def _remove_keyword_occurrence(content: str, keyword: str) -> str:
    updated = content.replace(keyword, " ")
    return " ".join(updated.split())
