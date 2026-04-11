from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from app.models.analytics import Alert, OperationLog
from app.models.account import Account
from app.models.risk import AccountRiskConfig, ReplyHistory, RiskKeyword
from app.schemas.risk import (
    AccountRiskScheduleRequest,
    RiskKeywordCreateRequest,
    RiskKeywordUpdateRequest,
)
from app.services import risk_service


class TestRiskKeywordManagement:
    @pytest.mark.asyncio
    async def test_list_keywords_includes_system_and_merchant_scope(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())

        db.add_all(
            [
                RiskKeyword(
                    merchant_id=None,
                    keyword="禁用词",
                    category="platform_banned",
                    severity="block",
                    match_mode="exact",
                    is_active=True,
                ),
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword="商家词",
                    category="custom",
                    severity="warn",
                    match_mode="fuzzy",
                    is_active=True,
                ),
                RiskKeyword(
                    merchant_id=str(uuid4()),
                    keyword="其他商家",
                    category="custom",
                    severity="block",
                    match_mode="exact",
                    is_active=True,
                ),
            ]
        )
        await db.flush()

        items = await risk_service.list_keywords(
            merchant_id=merchant_id,
            category=None,
            is_active=True,
            db=db,
        )

        assert [(item.merchant_id, item.keyword) for item in items] == [
            (merchant_id, "商家词"),
            (None, "禁用词"),
        ]

    @pytest.mark.asyncio
    async def test_create_keyword_rejects_duplicate_in_same_scope(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        request = RiskKeywordCreateRequest(
            keyword="敏感词",
            category="custom",
            replacement="替换词",
            match_mode="exact",
            severity="warn",
            is_active=True,
        )

        await risk_service.create_keyword(merchant_id, request, db)

        with pytest.raises(HTTPException) as exc_info:
            await risk_service.create_keyword(merchant_id, request, db)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_update_keyword_rejects_duplicate_target(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        first = await risk_service.create_keyword(
            merchant_id,
            RiskKeywordCreateRequest(
                keyword="词A",
                category="custom",
                replacement=None,
                match_mode="exact",
                severity="block",
                is_active=True,
            ),
            db,
        )
        second = await risk_service.create_keyword(
            merchant_id,
            RiskKeywordCreateRequest(
                keyword="词B",
                category="custom",
                replacement=None,
                match_mode="exact",
                severity="block",
                is_active=True,
            ),
            db,
        )

        with pytest.raises(HTTPException) as exc_info:
            await risk_service.update_keyword(
                merchant_id,
                second.id,
                RiskKeywordUpdateRequest(keyword=first.keyword, category=first.category),
                db,
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_update_and_delete_keyword_only_affect_own_merchant_record(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        other_merchant_id = str(uuid4())
        created = await risk_service.create_keyword(
            merchant_id,
            RiskKeywordCreateRequest(
                keyword="原词",
                category="custom",
                replacement=None,
                match_mode="exact",
                severity="block",
                is_active=True,
            ),
            db,
        )

        updated = await risk_service.update_keyword(
            merchant_id,
            created.id,
            RiskKeywordUpdateRequest(
                keyword="新词",
                replacement="建议词",
                severity="warn",
                is_active=False,
            ),
            db,
        )

        assert updated.keyword == "新词"
        assert updated.replacement == "建议词"
        assert updated.severity == "warn"
        assert updated.is_active is False

        with pytest.raises(HTTPException) as update_exc:
            await risk_service.update_keyword(
                other_merchant_id,
                created.id,
                RiskKeywordUpdateRequest(keyword="越权"),
                db,
            )
        assert update_exc.value.status_code == 404

        with pytest.raises(HTTPException) as delete_exc:
            await risk_service.delete_keyword(other_merchant_id, created.id, db)
        assert delete_exc.value.status_code == 404

        await risk_service.delete_keyword(merchant_id, created.id, db)

        items = await risk_service.list_keywords(
            merchant_id=merchant_id,
            category=None,
            is_active=None,
            db=db,
        )
        assert items == []


class TestSensitiveKeywordScan:
    @pytest.mark.asyncio
    async def test_scan_sensitive_keywords_returns_system_and_merchant_hits(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        db.add_all(
            [
                RiskKeyword(
                    merchant_id=None,
                    keyword="forbidden",
                    category="platform_banned",
                    replacement="allowed",
                    match_mode="exact",
                    severity="block",
                    is_active=True,
                ),
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword="promo",
                    category="custom",
                    replacement="intro",
                    match_mode="exact",
                    severity="warn",
                    is_active=True,
                ),
            ]
        )
        await db.flush()

        hits = await risk_service.scan_sensitive_keywords(
            "forbidden promo content",
            merchant_id,
            db,
        )

        assert [(item.keyword, item.start, item.end, item.severity) for item in hits] == [
            ("forbidden", 0, 9, "block"),
            ("promo", 10, 15, "warn"),
        ]
        assert hits[0].replacement == "allowed"
        assert hits[1].replacement == "intro"

    @pytest.mark.asyncio
    async def test_scan_sensitive_keywords_prefers_merchant_keyword_on_duplicate_definition(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        db.add_all(
            [
                RiskKeyword(
                    merchant_id=None,
                    keyword="sale",
                    category="custom",
                    replacement="campaign",
                    match_mode="exact",
                    severity="block",
                    is_active=True,
                ),
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword="sale",
                    category="custom",
                    replacement="offer",
                    match_mode="exact",
                    severity="warn",
                    is_active=True,
                ),
            ]
        )
        await db.flush()

        hits = await risk_service.scan_sensitive_keywords("flash sale today", merchant_id, db)

        assert len(hits) == 1
        assert hits[0].keyword == "sale"
        assert hits[0].replacement == "offer"
        assert hits[0].severity == "warn"

    @pytest.mark.asyncio
    async def test_scan_sensitive_keywords_supports_fuzzy_match_mode(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        db.add(
            RiskKeyword(
                merchant_id=merchant_id,
                keyword="brand",
                category="custom",
                replacement=None,
                match_mode="fuzzy",
                severity="warn",
                is_active=True,
            )
        )
        await db.flush()

        hits = await risk_service.scan_sensitive_keywords("bramd mention", merchant_id, db)

        assert len(hits) == 1
        assert hits[0].keyword == "brand"
        assert hits[0].start == 0
        assert hits[0].end == 5

    @pytest.mark.asyncio
    async def test_scan_sensitive_keywords_ignores_inactive_and_other_merchant_keywords(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        db.add_all(
            [
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword="ignoreme",
                    category="custom",
                    replacement=None,
                    match_mode="exact",
                    severity="block",
                    is_active=False,
                ),
                RiskKeyword(
                    merchant_id=str(uuid4()),
                    keyword="othermerchant",
                    category="custom",
                    replacement=None,
                    match_mode="exact",
                    severity="block",
                    is_active=True,
                ),
            ]
        )
        await db.flush()

        hits = await risk_service.scan_sensitive_keywords(
            "ignoreme othermerchant",
            merchant_id,
            db,
        )

        assert hits == []


class TestInboundRiskScan:
    @pytest.mark.asyncio
    async def test_scan_input_returns_passed_with_hits_and_emits_alert(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="inbound-test",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            RiskKeyword(
                merchant_id=None,
                keyword="forbidden",
                category="platform_banned",
                replacement="allowed",
                match_mode="exact",
                severity="block",
                is_active=True,
            )
        )
        await db.flush()

        with patch("app.services.risk_service.send_alert", new=AsyncMock()) as mocked_alert:
            result = await risk_service.scan_input(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="comment_inbound",
                content="forbidden words from user",
                db=db,
            )

        assert result.passed is True
        assert result.decision == "passed"
        assert len(result.hits) == 1
        assert result.hits[0].keyword == "forbidden"
        mocked_alert.assert_awaited_once()

        log_result = await db.execute(select(OperationLog))
        logs = log_result.scalars().all()
        assert len(logs) == 1
        assert logs[0].operation_type == "comment_inbound"
        assert logs[0].detail["violations"] == ["forbidden"]

        alert_result = await db.execute(select(Alert))
        alerts = alert_result.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].alert_type == "inbound_risk_hit"
        assert alerts[0].module == "E"

    @pytest.mark.asyncio
    async def test_scan_input_clean_content_does_not_emit_alert(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="clean-inbound",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with patch("app.services.risk_service.send_alert", new=AsyncMock()) as mocked_alert:
            result = await risk_service.scan_input(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="dm_inbound",
                content="normal hello there",
                db=db,
            )

        assert result.passed is True
        assert result.decision == "passed"
        assert result.hits == []
        mocked_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_scan_input_rejects_invalid_scene(
        self,
        db: AsyncSession,
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await risk_service.scan_input(
                merchant_id=str(uuid4()),
                account_id=str(uuid4()),
                scene="comment_reply",
                content="anything",
                db=db,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_scan_input_checks_account_ownership(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        other_merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="owned-account",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with pytest.raises(HTTPException) as exc_info:
            await risk_service.scan_input(
                merchant_id=other_merchant_id,
                account_id=account.id,
                scene="comment_inbound",
                content="hello",
                db=db,
            )

        assert exc_info.value.status_code == 404


class TestOutboundRiskScan:
    @pytest.mark.asyncio
    async def test_scan_output_returns_blocked_for_blocking_keyword(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="blocked-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            RiskKeyword(
                merchant_id=None,
                keyword="forbidden",
                category="platform_banned",
                replacement="allowed",
                match_mode="exact",
                severity="block",
                is_active=True,
            )
        )
        await db.flush()

        result = await risk_service.scan_output(
            merchant_id=merchant_id,
            account_id=account.id,
            scene="comment_reply",
            content="forbidden outbound content",
            db=db,
        )

        assert result.passed is False
        assert result.decision == "blocked"
        assert len(result.hits) == 1
        assert result.retryable is False

        log_result = await db.execute(select(OperationLog))
        logs = log_result.scalars().all()
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].detail["risk_decision"] == "blocked"
        assert logs[0].detail["violations"] == ["forbidden"]

    @pytest.mark.asyncio
    async def test_scan_output_returns_rewrite_required_for_warn_only_hits(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="rewrite-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
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

        result = await risk_service.scan_output(
            merchant_id=merchant_id,
            account_id=account.id,
            scene="dm_send",
            content="promo outbound content",
            db=db,
        )

        assert result.passed is False
        assert result.decision == "rewrite_required"
        assert len(result.hits) == 1
        assert result.retryable is True

    @pytest.mark.asyncio
    async def test_scan_output_returns_passed_when_checks_are_clean(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="passed-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        result = await risk_service.scan_output(
            merchant_id=merchant_id,
            account_id=account.id,
            scene="note_publish",
            content="clean outbound content",
            db=db,
        )

        assert result.passed is True
        assert result.decision == "passed"
        assert result.hits == []
        assert result.retryable is False

    @pytest.mark.asyncio
    async def test_scan_output_short_circuits_on_rest_window_decision(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="rest-window-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        blocked_decision = risk_service.RiskScanResponse(
            passed=False,
            decision="blocked",
            hits=[],
            retryable=False,
        )
        with patch(
            "app.services.risk_service._check_rest_window_for_output",
            new=AsyncMock(return_value=blocked_decision),
        ) as mocked_rest, patch(
            "app.services.risk_service._check_quota_for_output",
            new=AsyncMock(),
        ) as mocked_quota:
            result = await risk_service.scan_output(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="comment_reply",
                content="anything",
                db=db,
            )

        assert result.decision == "blocked"
        mocked_rest.assert_awaited_once()
        mocked_quota.assert_not_awaited()

        log_result = await db.execute(select(OperationLog))
        logs = log_result.scalars().all()
        assert len(logs) == 1
        assert logs[0].error_code == "rest_window_blocked"
        assert logs[0].detail["reason"] == "rest_window"

    @pytest.mark.asyncio
    async def test_scan_output_rejects_invalid_scene(
        self,
        db: AsyncSession,
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await risk_service.scan_output(
                merchant_id=str(uuid4()),
                account_id=str(uuid4()),
                scene="comment_inbound",
                content="anything",
                db=db,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_scan_output_checks_account_ownership(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        other_merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="owned-outbound",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with pytest.raises(HTTPException) as exc_info:
            await risk_service.scan_output(
                merchant_id=other_merchant_id,
                account_id=account.id,
                scene="comment_reply",
                content="hello there",
                db=db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_scan_output_runs_task4_stage_order(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="ordered-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        stage_calls: list[str] = []
        with patch(
            "app.services.risk_service._check_rest_window_for_output",
            new=AsyncMock(side_effect=lambda *args, **kwargs: stage_calls.append("rest_window") or None),
        ), patch(
            "app.services.risk_service._check_quota_for_output",
            new=AsyncMock(side_effect=lambda *args, **kwargs: stage_calls.append("quota") or None),
        ), patch(
            "app.services.risk_service.scan_sensitive_keywords",
            new=AsyncMock(side_effect=lambda *args, **kwargs: stage_calls.append("sensitive_keywords") or []),
        ), patch(
            "app.services.risk_service._check_competitor_for_output",
            new=AsyncMock(side_effect=lambda *args, **kwargs: stage_calls.append("competitor_keywords") or None),
        ), patch(
            "app.services.risk_service._check_similarity_for_output",
            new=AsyncMock(
                side_effect=lambda *args, **kwargs: (
                    stage_calls.append("reply_similarity")
                    or risk_service.RiskScanResponse(
                        passed=False,
                        decision="rewrite_required",
                        hits=[],
                        retryable=True,
                    )
                )
            ),
        ):
            result = await risk_service.scan_output(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="comment_reply",
                content="clean content",
                db=db,
            )

        assert stage_calls == list(risk_service.OUTBOUND_SCAN_ORDER)
        assert result.decision == "rewrite_required"
        assert result.hits == []


class TestQuotaReservation:
    @pytest.mark.asyncio
    async def test_check_and_reserve_quota_uses_default_limits(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="quota-default",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock()
        with patch("app.services.risk_service.get_redis", return_value=redis):
            allowed = await risk_service.check_and_reserve_quota(
                account_id=account.id,
                action="comment_reply",
                db=db,
            )

        assert allowed is True
        redis.incr.assert_awaited_once()
        redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_and_reserve_quota_honors_account_specific_limits(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="quota-custom",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            AccountRiskConfig(
                account_id=account.id,
                comment_reply_limit_per_hour=2,
                dm_send_limit_per_hour=9,
                note_publish_limit_per_day=1,
            )
        )
        await db.flush()

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=2)
        redis.expire = AsyncMock()
        with patch("app.services.risk_service.get_redis", return_value=redis):
            allowed = await risk_service.check_and_reserve_quota(
                account_id=account.id,
                action="comment_reply",
                db=db,
            )

        assert allowed is True

    @pytest.mark.asyncio
    async def test_check_and_reserve_quota_sends_alert_when_exceeded(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="quota-exceeded",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            AccountRiskConfig(
                account_id=account.id,
                comment_reply_limit_per_hour=1,
                dm_send_limit_per_hour=50,
                note_publish_limit_per_day=3,
            )
        )
        await db.flush()

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=2)
        redis.expire = AsyncMock()
        with patch("app.services.risk_service.get_redis", return_value=redis), patch(
            "app.services.risk_service.send_alert",
            new=AsyncMock(),
        ) as mocked_alert:
            allowed = await risk_service.check_and_reserve_quota(
                account_id=account.id,
                action="comment_reply",
                db=db,
            )

        assert allowed is False
        mocked_alert.assert_awaited_once()

        alert_result = await db.execute(select(Alert))
        alerts = alert_result.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].alert_type == "risk_quota_exceeded"

    @pytest.mark.asyncio
    async def test_scan_output_returns_blocked_when_quota_is_exceeded(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="quota-blocked-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with patch(
            "app.services.risk_service._check_rest_window_for_output",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.services.risk_service.get_redis",
            return_value=AsyncMock(
                incr=AsyncMock(return_value=21),
                expire=AsyncMock(),
            ),
        ), patch(
            "app.services.risk_service.send_alert",
            new=AsyncMock(),
        ):
            result = await risk_service.scan_output(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="comment_reply",
                content="clean content",
                db=db,
            )

        assert result.passed is False
        assert result.decision == "blocked"


class TestRestWindowSchedule:
    @pytest.mark.asyncio
    async def test_update_account_schedule_upserts_and_caches_windows(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="rest-schedule",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        redis = AsyncMock()
        redis.setex = AsyncMock()
        with patch("app.services.risk_service.get_redis", return_value=redis):
            config = await risk_service.update_account_schedule(
                merchant_id=merchant_id,
                account_id=account.id,
                data=AccountRiskScheduleRequest(rest_windows=["00:00-08:00", "13:00-14:00"]),
                db=db,
            )

        assert config.account_id == account.id
        assert config.rest_windows == ["00:00-08:00", "13:00-14:00"]
        redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_account_schedule_checks_account_ownership(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        other_merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="rest-schedule-owned",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with pytest.raises(HTTPException) as exc_info:
            await risk_service.update_account_schedule(
                merchant_id=other_merchant_id,
                account_id=account.id,
                data=AccountRiskScheduleRequest(rest_windows=["00:00-08:00"]),
                db=db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_is_in_rest_window_uses_cached_windows(
        self,
        db: AsyncSession,
    ) -> None:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value='["00:00-08:00"]')
        with patch("app.services.risk_service.get_redis", return_value=redis):
            in_window = await risk_service.is_in_rest_window(
                account_id=str(uuid4()),
                now=datetime(2026, 4, 11, 1, 0, tzinfo=timezone.utc),
                db=db,
            )

        assert in_window is True
        redis.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_in_rest_window_loads_from_db_and_handles_cross_midnight(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="rest-db",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            AccountRiskConfig(
                account_id=account.id,
                rest_windows=["23:00-02:00"],
            )
        )
        await db.flush()

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        with patch("app.services.risk_service.get_redis", return_value=redis):
            in_window = await risk_service.is_in_rest_window(
                account_id=account.id,
                now=datetime(2026, 4, 11, 1, 30, tzinfo=timezone.utc),
                db=db,
            )

        assert in_window is True
        redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scan_output_returns_blocked_when_in_rest_window(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="rest-blocked-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with patch(
            "app.services.risk_service.is_in_rest_window",
            new=AsyncMock(return_value=True),
        ):
            result = await risk_service.scan_output(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="comment_reply",
                content="clean content",
                db=db,
            )

        assert result.passed is False
        assert result.decision == "blocked"


class TestHumanizedDelay:
    @pytest.mark.asyncio
    async def test_apply_humanized_delay_returns_value_in_expected_range(self) -> None:
        delay = await risk_service.apply_humanized_delay(
            account_id=str(uuid4()),
            action="comment_reply",
        )

        assert 3.0 <= delay <= 15.0

    @pytest.mark.asyncio
    async def test_apply_humanized_delay_uses_randomized_value(self) -> None:
        with patch("app.services.risk_service.random.uniform", return_value=8.236):
            delay = await risk_service.apply_humanized_delay(
                account_id=str(uuid4()),
                action="dm_send",
            )

        assert delay == 8.24

    @pytest.mark.asyncio
    async def test_apply_humanized_delay_rejects_invalid_action(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await risk_service.apply_humanized_delay(
                account_id=str(uuid4()),
                action="comment_inbound",
            )

        assert exc_info.value.status_code == 400


class TestSimilarityDetection:
    @pytest.mark.asyncio
    async def test_inject_variants_changes_content_shape(self) -> None:
        content = "您好，我们可以马上联系您"

        updated = risk_service.inject_variants(content)

        assert updated != content
        assert updated

    @pytest.mark.asyncio
    async def test_detect_similarity_returns_match_when_above_default_threshold(
        self,
        db: AsyncSession,
    ) -> None:
        account_id = str(uuid4())
        db.add(
            Account(
                id=account_id,
                merchant_id=str(uuid4()),
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="similarity-default",
                access_type="browser",
                status="active",
            )
        )
        db.add(
            ReplyHistory(
                account_id=account_id,
                content="感谢您联系我们，我们马上处理",
                normalized_content="感谢您联系我们我们马上处理",
                similarity_hash=None,
                source_type="comment_reply",
                source_record_id=None,
            )
        )
        await db.flush()

        result = await risk_service.detect_similarity(
            account_id=account_id,
            candidate="感谢您联系我们，我们马上处理",
            db=db,
        )

        assert result is not None
        assert result["similarity_score"] >= 0.85
        assert result["matched_history_id"]
        assert result["rewrite_suggestion"]

    @pytest.mark.asyncio
    async def test_detect_similarity_respects_account_specific_threshold(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="similarity-threshold",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            AccountRiskConfig(
                account_id=account.id,
                dedup_similarity_threshold=0.99,
            )
        )
        db.add(
            ReplyHistory(
                account_id=account.id,
                content="欢迎私信我了解详情",
                normalized_content="欢迎私信我了解详情",
                similarity_hash=None,
                source_type="dm_send",
                source_record_id=None,
            )
        )
        await db.flush()

        result = await risk_service.detect_similarity(
            account_id=account.id,
            candidate="欢迎私信我了解详情呀",
            db=db,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_scan_output_returns_rewrite_required_for_similar_reply_history(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="similarity-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            ReplyHistory(
                account_id=account.id,
                content="感谢留言，我们会尽快联系您",
                normalized_content="感谢留言我们会尽快联系您",
                similarity_hash=None,
                source_type="comment_reply",
                source_record_id=None,
            )
        )
        await db.flush()

        with patch(
            "app.services.risk_service._check_rest_window_for_output",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.services.risk_service._check_quota_for_output",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.services.risk_service._check_competitor_for_output",
            new=AsyncMock(return_value=None),
        ):
            result = await risk_service.scan_output(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="comment_reply",
                content="感谢留言，我们会尽快联系您",
                db=db,
            )

        assert result.passed is False
        assert result.decision == "rewrite_required"
        assert result.similarity_score is not None
        assert result.matched_history_id is not None

    @pytest.mark.asyncio
    async def test_persist_reply_history_writes_postgresql_and_cache_summary(
        self,
        db: AsyncSession,
    ) -> None:
        account_id = str(uuid4())
        db.add(
            Account(
                id=account_id,
                merchant_id=str(uuid4()),
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="persist-history",
                access_type="browser",
                status="active",
            )
        )
        await db.flush()

        redis = AsyncMock()
        redis.lpush = AsyncMock()
        redis.ltrim = AsyncMock()
        redis.expire = AsyncMock()
        with patch("app.services.risk_service.get_redis", return_value=redis):
            history = await risk_service.persist_reply_history(
                account_id=account_id,
                content="Thanks for your message, we will follow up soon.",
                source_type="comment_reply",
                source_record_id=None,
                db=db,
            )

        await db.refresh(history)

        assert history.content == "Thanks for your message, we will follow up soon."
        assert history.normalized_content == "thanks for your message we will follow up soon"
        assert history.similarity_hash
        redis.lpush.assert_awaited_once()
        redis.ltrim.assert_awaited_once_with(
            f"risk:reply_history:{account_id}",
            0,
            99,
        )
        redis.expire.assert_awaited_once_with(
            f"risk:reply_history:{account_id}",
            86400,
        )

        cache_payload = json.loads(redis.lpush.await_args.args[1])
        assert cache_payload["id"] == history.id
        assert cache_payload["normalized_content"] == history.normalized_content
        assert "content" not in cache_payload

    @pytest.mark.asyncio
    async def test_detect_similarity_reads_recent_history_from_cache_first(
        self,
        db: AsyncSession,
    ) -> None:
        account_id = str(uuid4())
        db.add(
            Account(
                id=account_id,
                merchant_id=str(uuid4()),
                xhs_user_id=f"xhs_{uuid4().hex[:8]}",
                nickname="similarity-cache",
                access_type="browser",
                status="active",
            )
        )
        await db.flush()

        cached_history = [
            json.dumps(
                {
                    "id": str(uuid4()),
                    "normalized_content": "thanks for reaching out, we will contact you soon",
                    "similarity_hash": "cached-hash",
                }
            )
        ]
        redis = AsyncMock()
        redis.lrange = AsyncMock(return_value=cached_history)
        with patch("app.services.risk_service.get_redis", return_value=redis):
            result = await risk_service.detect_similarity(
                account_id=account_id,
                candidate="Thanks for reaching out, we will contact you soon.",
                db=db,
            )

        assert result is not None
        assert result["matched_history_id"]
        redis.lrange.assert_awaited_once_with(f"risk:reply_history:{account_id}", 0, 99)


class TestCompetitorDetection:
    @pytest.mark.asyncio
    async def test_scan_sensitive_keywords_excludes_competitor_category(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        db.add(
            RiskKeyword(
                merchant_id=merchant_id,
                keyword="brandx",
                category="competitor",
                replacement="our brand",
                match_mode="exact",
                severity="warn",
                is_active=True,
            )
        )
        await db.flush()

        hits = await risk_service.scan_sensitive_keywords(
            content="compare brandx today",
            merchant_id=merchant_id,
            db=db,
        )

        assert hits == []

    @pytest.mark.asyncio
    async def test_scan_competitor_keywords_supports_whole_word_match(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        db.add(
            RiskKeyword(
                merchant_id=merchant_id,
                keyword="brandx",
                category="competitor",
                replacement="our brand",
                match_mode="exact",
                severity="warn",
                is_active=True,
            )
        )
        await db.flush()

        hits = await risk_service.scan_competitor_keywords(
            content="compare brandx today",
            merchant_id=merchant_id,
            db=db,
        )

        assert len(hits) == 1
        assert hits[0].keyword == "brandx"

    @pytest.mark.asyncio
    async def test_scan_competitor_keywords_supports_edit_distance_one(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        db.add(
            RiskKeyword(
                merchant_id=None,
                keyword="brandx",
                category="competitor",
                replacement=None,
                match_mode="fuzzy",
                severity="warn",
                is_active=True,
            )
        )
        await db.flush()

        hits = await risk_service.scan_competitor_keywords(
            content="we saw brndx in comments",
            merchant_id=merchant_id,
            db=db,
        )

        assert len(hits) == 1
        assert hits[0].keyword == "brandx"

    @pytest.mark.asyncio
    async def test_scan_output_returns_rewrite_required_for_competitor_hits(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="competitor-output",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            RiskKeyword(
                merchant_id=merchant_id,
                keyword="brandx",
                category="competitor",
                replacement="our brand",
                match_mode="exact",
                severity="warn",
                is_active=True,
            )
        )
        await db.flush()

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock()
        redis.incrby = AsyncMock(return_value=1)
        with patch(
            "app.services.risk_service._check_rest_window_for_output",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.services.risk_service._check_quota_for_output",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.services.risk_service.get_redis",
            return_value=redis,
        ):
            result = await risk_service.scan_output(
                merchant_id=merchant_id,
                account_id=account.id,
                scene="comment_reply",
                content="compare brandx today",
                db=db,
            )

        assert result.passed is False
        assert result.decision == "rewrite_required"
        assert result.hits
        assert result.hits[0].category == "competitor"
        redis.incrby.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_competitor_hits_trigger_alert_after_threshold(
        self,
        db: AsyncSession,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="competitor-alert",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            AccountRiskConfig(
                account_id=account.id,
                competitor_alert_threshold_per_hour=10,
            )
        )
        await db.flush()

        redis = AsyncMock()
        redis.incrby = AsyncMock(return_value=11)
        redis.expire = AsyncMock()
        with patch("app.services.risk_service.get_redis", return_value=redis), patch(
            "app.services.risk_service.send_alert",
            new=AsyncMock(),
        ) as mocked_alert:
            total = await risk_service._track_competitor_hits(
                merchant_id=merchant_id,
                account_id=account.id,
                hit_count=1,
                db=db,
            )

        assert total == 11
        mocked_alert.assert_awaited_once()

        alert_result = await db.execute(select(Alert))
        alerts = alert_result.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].alert_type == "competitor_hits_abnormal"
