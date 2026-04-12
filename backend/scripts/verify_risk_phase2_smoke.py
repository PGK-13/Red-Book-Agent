"""Phase 2 smoke verification for Module E."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.models.account import Account
from app.models.analytics import OperationLog
from app.models.content import ContentDraft
from app.models.risk import ReplyHistory, RiskKeyword
from app.services import content_service, interaction_service


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    merchant_id = str(uuid4())
    async with session_factory() as session:
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="phase2-smoke",
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
        session.add_all([account, draft])
        session.add(
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
        session.add(
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
        await session.flush()

        content_result = await content_service.review_draft_outbound_risk(
            merchant_id=merchant_id,
            draft_id=draft.id,
            db=session,
        )
        blocked_dm = await interaction_service.send_dm(
            merchant_id=merchant_id,
            account_id=account.id,
            content="forbidden outbound text",
            source_record_id=str(uuid4()),
            db=session,
        )
        reply_result = await interaction_service.send_comment_reply(
            merchant_id=merchant_id,
            account_id=account.id,
            content="thanks for reaching out",
            source_record_id=str(uuid4()),
            db=session,
        )
        await session.commit()

        logs = (
            await session.execute(
                select(OperationLog)
                .where(OperationLog.account_id == account.id)
                .order_by(OperationLog.created_at.asc())
            )
        ).scalars().all()
        histories = (
            await session.execute(select(ReplyHistory).where(ReplyHistory.account_id == account.id))
        ).scalars().all()

    await engine.dispose()

    assert content_result.decision.decision == "passed"
    assert content_result.attempts_used == 1
    assert blocked_dm.decision.decision == "blocked"
    assert blocked_dm.delivered is False
    assert reply_result.delivered is True
    assert len(histories) == 1
    assert any(log.detail["risk_decision"] == "rewrite_required" for log in logs)
    assert any(log.detail["risk_decision"] == "blocked" for log in logs)
    assert any(log.detail["risk_decision"] == "passed" for log in logs)
    assert all(log.detail["detail_schema"] == "module_e_risk_event.v1" for log in logs)
    print("Module E Phase 2 smoke verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
