from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.content import ContentDraft
from app.schemas.risk import RiskHitResponse, RiskScanResponse
from app.services import content_service


class TestContentDraftOutboundRisk:
    @pytest.mark.asyncio
    async def test_review_draft_marks_passed_when_scan_passes(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="content-pass",
            access_type="browser",
            status="active",
        )
        draft = ContentDraft(
            account_id=account.id,
            title="Clean title",
            body="Clean body",
            alt_titles=["Clean alt title"],
            hashtags=["safe-tag"],
            risk_status="pending",
            status="draft",
        )
        db.add_all([account, draft])
        await db.flush()

        with patch(
            "app.services.content_service.risk_service.scan_output",
            new=AsyncMock(
                return_value=RiskScanResponse(
                    passed=True,
                    decision="passed",
                    hits=[],
                    retryable=False,
                )
            ),
        ) as mocked_scan:
            result = await content_service.review_draft_outbound_risk(
                merchant_id=merchant_id,
                draft_id=draft.id,
                db=db,
            )

        assert result.decision.decision == "passed"
        assert result.attempts_used == 0
        assert draft.risk_status == "passed"
        mocked_scan.assert_awaited_once()
        assert "Clean alt title" in mocked_scan.await_args.kwargs["content"]

    @pytest.mark.asyncio
    async def test_review_draft_rewrites_and_passes_within_retry_budget(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="content-rewrite",
            access_type="browser",
            status="active",
        )
        draft = ContentDraft(
            account_id=account.id,
            title="promo title",
            body="Body with promo copy",
            alt_titles=["promo alt"],
            hashtags=["promo-tag"],
            risk_status="pending",
            status="draft",
        )
        db.add_all([account, draft])
        await db.flush()

        with patch(
            "app.services.content_service.risk_service.scan_output",
            new=AsyncMock(
                side_effect=[
                    RiskScanResponse(
                        passed=False,
                        decision="rewrite_required",
                        hits=[
                            RiskHitResponse(
                                keyword="promo",
                                category="custom",
                                start=0,
                                end=5,
                                replacement="intro",
                                severity="warn",
                            )
                        ],
                        retryable=True,
                    ),
                    RiskScanResponse(
                        passed=True,
                        decision="passed",
                        hits=[],
                        retryable=False,
                    ),
                ]
            ),
        ) as mocked_scan:
            result = await content_service.review_draft_outbound_risk(
                merchant_id=merchant_id,
                draft_id=draft.id,
                db=db,
            )

        assert result.decision.decision == "passed"
        assert result.attempts_used == 1
        assert draft.risk_status == "passed"
        assert draft.title == "intro title"
        assert "intro" in draft.body
        assert draft.alt_titles == ["intro alt"]
        assert draft.hashtags == ["intro-tag"]
        assert mocked_scan.await_count == 2

    @pytest.mark.asyncio
    async def test_review_draft_marks_manual_review_after_three_failed_rewrites(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="content-manual-review",
            access_type="browser",
            status="active",
        )
        draft = ContentDraft(
            account_id=account.id,
            title="promo title",
            body="Body with promo copy",
            alt_titles=["promo alt"],
            hashtags=["promo-tag"],
            risk_status="pending",
            status="draft",
        )
        db.add_all([account, draft])
        await db.flush()

        rewrite_required = RiskScanResponse(
            passed=False,
            decision="rewrite_required",
            hits=[
                RiskHitResponse(
                    keyword="promo",
                    category="custom",
                    start=0,
                    end=5,
                    replacement=None,
                    severity="warn",
                )
            ],
            retryable=True,
        )
        with patch(
            "app.services.content_service.risk_service.scan_output",
            new=AsyncMock(
                side_effect=[
                    rewrite_required,
                    rewrite_required,
                    rewrite_required,
                    rewrite_required,
                ]
            ),
        ) as mocked_scan, patch(
            "app.services.content_service.risk_service.emit_alert_if_needed",
            new=AsyncMock(),
        ) as mocked_alert:
            result = await content_service.review_draft_outbound_risk(
                merchant_id=merchant_id,
                draft_id=draft.id,
                db=db,
            )

        assert result.decision.decision == "manual_review"
        assert result.attempts_used == 3
        assert draft.risk_status == "manual_review"
        assert draft.title == "promo title"
        assert draft.body == "Body with promo copy"
        assert draft.alt_titles == ["promo alt"]
        assert draft.hashtags == ["promo-tag"]
        assert mocked_scan.await_count == 4
        mocked_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_draft_real_risk_flow_rewrites_then_passes(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="content-real-risk",
            access_type="browser",
            status="active",
        )
        draft = ContentDraft(
            account_id=account.id,
            title="promo title",
            body="promo body copy",
            alt_titles=["promo alt"],
            hashtags=["promo-tag"],
            risk_status="pending",
            status="draft",
        )
        db.add_all([account, draft])
        from app.models.risk import RiskKeyword

        db.add(
            RiskKeyword(
                merchant_id=merchant_id,
                keyword="promo",
                category="custom",
                replacement="intro",
                match_mode="exact",
                severity="warn",
                is_active=True,
            )
        )
        await db.flush()

        result = await content_service.review_draft_outbound_risk(
            merchant_id=merchant_id,
            draft_id=draft.id,
            db=db,
        )

        assert result.decision.decision == "passed"
        assert result.attempts_used == 1
        assert draft.risk_status == "passed"
        assert "intro" in draft.title
        assert "intro" in draft.body
