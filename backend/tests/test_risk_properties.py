from __future__ import annotations

import string
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.risk import ReplyHistory, RiskKeyword
from app.services import risk_service


def _unique_keywords_strategy():
    return st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=3, max_size=8),
        min_size=1,
        max_size=5,
        unique=True,
    ).filter(
        lambda items: all(
            left not in right and right not in left
            for index, left in enumerate(items)
            for right in items[index + 1 :]
        )
    )


def _phrase_strategy():
    alphabet = string.ascii_lowercase + "     "
    return st.text(alphabet=alphabet, min_size=8, max_size=40).map(
        lambda value: " ".join(value.split()) or "safe reply"
    )


class TestRiskProperties:
    @pytest.mark.asyncio
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(keywords=_unique_keywords_strategy())
    async def test_property_13_outbound_content_is_scanned_before_send(
        self,
        db: AsyncSession,
        keywords: list[str],
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="property-13",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add_all(
            [
                RiskKeyword(
                    merchant_id=merchant_id,
                    keyword=keyword,
                    category="custom",
                    replacement=f"{keyword}_alt",
                    match_mode="exact",
                    severity="warn",
                    is_active=True,
                )
                for keyword in keywords
            ]
        )
        await db.flush()

        content = " | ".join(keywords)

        hits = await risk_service.scan_sensitive_keywords(content, merchant_id, db)
        decision = await risk_service.scan_output(
            merchant_id=merchant_id,
            account_id=account.id,
            scene="comment_reply",
            content=content,
            db=db,
        )

        assert {hit.keyword for hit in hits} == set(keywords)
        assert all(content[hit.start : hit.end] == hit.keyword for hit in hits)
        assert decision.decision == "rewrite_required"
        assert decision.retryable is True

    @pytest.mark.asyncio
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        action=st.sampled_from(["comment_reply", "dm_send", "note_publish"]),
        attempts=st.integers(min_value=1, max_value=60),
    )
    async def test_property_14_operation_rate_caps_are_never_exceeded(
        self,
        db: AsyncSession,
        action: str,
        attempts: int,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="property-14",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        limit = {
            "comment_reply": 20,
            "dm_send": 50,
            "note_publish": 3,
        }[action]
        redis = AsyncMock()
        redis.incr = AsyncMock(side_effect=list(range(1, attempts + 1)))
        redis.expire = AsyncMock()

        with patch("app.services.risk_service.get_redis", return_value=redis), patch(
            "app.services.risk_service.send_alert",
            new=AsyncMock(),
        ):
            results = [
                await risk_service.check_and_reserve_quota(
                    account_id=account.id,
                    action=action,
                    db=db,
                )
                for _ in range(attempts)
            ]

        expected = [index <= limit for index in range(1, attempts + 1)]
        assert results == expected

    @pytest.mark.asyncio
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(base_text=_phrase_strategy())
    async def test_property_15_high_similarity_replies_trigger_rewrite(
        self,
        db: AsyncSession,
        base_text: str,
    ) -> None:
        merchant_id = str(uuid4())
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="property-15",
            access_type="browser",
            status="active",
        )
        db.add(account)
        db.add(
            ReplyHistory(
                account_id=account.id,
                content=base_text,
                normalized_content=risk_service._normalize_similarity_text(base_text),
                similarity_hash=None,
                source_type="comment_reply",
                source_record_id=None,
            )
        )
        await db.flush()

        candidate = f"  {base_text.upper()}!!!  "

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
                content=candidate,
                db=db,
            )

        assert result.decision == "rewrite_required"
        assert result.similarity_score is not None
        assert result.similarity_score >= 0.85
        assert result.matched_history_id is not None
