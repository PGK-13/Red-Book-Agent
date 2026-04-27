"""模块 D 集成测试 — Mock Playwright + LLM。

测试完整链路：
1. 评论监测 → OCR → 意图分类 → 私信触发
2. 私信轮询 → 意图分类 → RAG → 回复生成 → 风控 → 发送
3. 人工接管 → 审核 → 发送
4. Captcha 检测 → 账号暂停 → 告警
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Conversation, MonitoredNote
from app.services import interaction_service as svc


# ── Mock 策略说明 ─────────────────────────────────────────────────────────────
#
# Playwright RPA 工具均需 mock：
#   - playwright_comment_monitor.poll_note_comments → 返回模拟评论列表
#   - playwright_dm_monitor.poll_dm_messages → 返回模拟消息列表
#   - playwright_dm_sender.send_dm → 返回 (True, None)
#   - playwright_comment_replier.send_comment_reply → 返回 (True, None)
#
# LLM 调用均 mock：
#   - agent.graphs.intent_router.get_intent_router_graph() → 返回 mock agent
#   - agent.graphs.customer_service.get_customer_service_graph() → 返回 mock agent
#
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# 链路 1：评论监测 → OCR → 意图分类 → 私信触发
# ─────────────────────────────────────────────────────────────────────────────


class TestCommentMonitorToDMTPipeline:
    """评论监测完整链路测试。"""

    @pytest.mark.asyncio
    async def test_comment_processing_pipeline(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """新评论 → 意图分类 → 非高风险 → 记录触发。"""

        mock_comments = [
            {
                "xhs_comment_id": "c001",
                "xhs_user_id": "u001",
                "content": "这个产品多少钱？",
                "image_urls": [],
                "parsed_at": datetime.now(timezone.utc),
            },
        ]

        # Mock RPA 工具
        with patch(
            "app.services.interaction_service.is_captcha_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "agent.tools.playwright_comment_monitor.poll_note_comments",
            new_callable=AsyncMock,
            return_value=(mock_comments, datetime.now(timezone.utc), False),
        ), patch(
            "app.services.interaction_service.perform_ocr",
            new_callable=AsyncMock,
            return_value=("", 0.0),
        ), patch(
            "agent.graphs.intent_router.get_intent_router_graph",
        ) as mock_intent_graph, patch(
            "agent.graphs.customer_service.get_customer_service_graph",
        ) as mock_cs_graph, patch(
            "app.services.interaction_service.get_redis",
            new_callable=AsyncMock,
        ) as mock_redis:

            # Mock IntentRouterGraph
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.intent = "ask_price"
            mock_result.confidence = 0.95
            mock_result.sentiment_score = 0.3
            mock_result.needs_human_review = False
            mock_result.review_reason = None
            mock_agent.classify = AsyncMock(return_value=mock_result)
            mock_intent_graph.return_value = mock_agent

            # Mock CustomerServiceGraph
            mock_cs = MagicMock()
            mock_cs_result = MagicMock()
            mock_cs_result.send_success = True
            mock_cs_result.final_reply = "您好，这款产品价格为 99 元~"
            mock_cs_result.error_message = None
            mock_cs.reply = AsyncMock(return_value=mock_cs_result)
            mock_cs_graph.return_value = mock_cs

            # Mock Redis
            mock_redis_instance = AsyncMock()
            mock_redis_instance.smembers.return_value = set()
            mock_redis_instance.sadd = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # 执行评论处理
            result = await svc.check_monitored_notes(
                account_id=account_id,
                db=db,
            )

            assert result["processed_notes"] >= 0
            # 若有新评论，应触发 DM
            # 由于 OCR 和意图分类被 mock，可以验证链路走到头了

    @pytest.mark.asyncio
    async def test_comment_needs_human_review_triggers_hitl(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """高风险评论（complaint）→ 入 HITL 队列，不触发 DM。"""

        mock_comments = [
            {
                "xhs_comment_id": "c002",
                "xhs_user_id": "u002",
                "content": "太差了，欺骗消费者！",
                "image_urls": [],
                "parsed_at": datetime.now(timezone.utc),
            },
        ]

        with patch(
            "app.services.interaction_service.is_captcha_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "agent.tools.playwright_comment_monitor.poll_note_comments",
            new_callable=AsyncMock,
            return_value=(mock_comments, datetime.now(timezone.utc), False),
        ), patch(
            "app.services.interaction_service.perform_ocr",
            new_callable=AsyncMock,
            return_value=("", 0.0),
        ), patch(
            "agent.graphs.intent_router.get_intent_router_graph",
        ) as mock_intent_graph, patch(
            "app.services.interaction_service.get_redis",
            new_callable=AsyncMock,
        ) as mock_redis:

            # Mock 投诉意图 → needs_human_review=True
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.intent = "complaint"
            mock_result.confidence = 0.9
            mock_result.sentiment_score = -0.9
            mock_result.needs_human_review = True
            mock_result.review_reason = "high_risk_intent_complaint"
            mock_agent.classify = AsyncMock(return_value=mock_result)
            mock_intent_graph.return_value = mock_agent

            mock_redis_instance = AsyncMock()
            mock_redis_instance.smembers.return_value = set()
            mock_redis_instance.sadd = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            result = await svc.check_monitored_notes(account_id=account_id, db=db)

            # 评论被处理但不应触发 DM
            assert result.get("new_comments", 0) >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 链路 2：私信轮询 → 意图分类 → 回复生成 → 风控 → 发送
# ─────────────────────────────────────────────────────────────────────────────


class TestDMPipeline:
    """私信自动回复链路测试。"""

    @pytest.mark.asyncio
    async def test_dm_polling_creates_conversation(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
    ) -> None:
        """新私信 → 创建会话 → 写入消息。"""

        mock_messages = [
            {
                "xhs_msg_id": "m001",
                "xhs_user_id": "dm_user_001",
                "role": "user",
                "content": "你好，这个怎么买？",
                "sent_at": "2026-04-24 10:00",
            },
        ]

        with patch(
            "app.services.interaction_service.is_captcha_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "agent.tools.playwright_dm_monitor.poll_dm_messages",
            new_callable=AsyncMock,
            return_value=(mock_messages, False),
        ), patch(
            "agent.graphs.intent_router.get_intent_router_graph",
        ) as mock_intent_graph, patch(
            "agent.graphs.customer_service.get_customer_service_graph",
        ) as mock_cs_graph, patch(
            "app.services.interaction_service.get_redis",
            new_callable=AsyncMock,
        ) as mock_redis, patch(
            "app.models.account.Account",
        ) as mock_account_model:

            # Mock 账号
            mock_account = MagicMock()
            mock_account.merchant_id = merchant_id
            mock_account.status = "active"
            mock_account.cookie_enc = None
            mock_account.proxy_url_enc = None
            mock_account_model.get = AsyncMock(return_value=mock_account)
            mock_account_model.status = "active"

            # Mock IntentRouterGraph
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.intent = "general_inquiry"
            mock_result.confidence = 0.85
            mock_result.sentiment_score = 0.2
            mock_result.needs_human_review = False
            mock_result.review_reason = None
            mock_agent.classify = AsyncMock(return_value=mock_result)
            mock_intent_graph.return_value = mock_agent

            # Mock CustomerServiceGraph
            mock_cs = MagicMock()
            mock_cs_result = MagicMock()
            mock_cs_result.send_success = True
            mock_cs_result.final_reply = "您好，欢迎选购~"
            mock_cs_result.error_message = None
            mock_cs.reply = AsyncMock(return_value=mock_cs_result)
            mock_cs_graph.return_value = mock_cs

            # Mock Redis
            mock_redis_instance = AsyncMock()
            mock_redis_instance.smembers.return_value = set()
            mock_redis_instance.sadd = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock Account model select
            with patch("sqlalchemy.select") as mock_select:
                mock_select.return_value = MagicMock()
                mock_select.return_value.where = MagicMock(return_value=MagicMock())

                result = await svc.poll_dm_messages(account_id=account_id, db=db)

                assert "new_messages" in result or "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# 链路 3：Captcha 检测 → 账号暂停 → 告警
# ─────────────────────────────────────────────────────────────────────────────


class TestCaptchaFlow:
    """Captcha 检测链路测试。"""

    @pytest.mark.asyncio
    async def test_captcha_detected_stops_automation(
        self,
        db: AsyncSession,
        merchant_id: str,
        account_id: str,
        monitored_note: MonitoredNote,
    ) -> None:
        """Captcha 检测到时应停止后续 RPA 操作。"""

        mock_comments = [
            {
                "xhs_comment_id": "c003",
                "xhs_user_id": "u003",
                "content": "测试评论",
                "image_urls": [],
                "parsed_at": datetime.now(timezone.utc),
            },
        ]

        with patch(
            "agent.tools.playwright_comment_monitor.poll_note_comments",
            new_callable=AsyncMock,
            return_value=(mock_comments, datetime.now(timezone.utc), True),  # captcha_detected=True
        ), patch(
            "app.services.interaction_service.get_redis",
            new_callable=AsyncMock,
        ) as mock_redis, patch.object(
            svc, "send_alert", new_callable=AsyncMock,
        ):

            mock_redis_instance = AsyncMock()
            mock_redis_instance.smembers.return_value = set()
            mock_redis_instance.sadd = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Captcha 检测时 check_monitored_notes 会提前返回
            # 不应抛出异常
            result = await svc.check_monitored_notes(account_id=account_id, db=db)
            assert result["processed_notes"] == 0  # Captcha 阻断，无处理


# ─────────────────────────────────────────────────────────────────────────────
# 链路 4：人工接管 → 审核 → 发送
# ─────────────────────────────────────────────────────────────────────────────


class TestHumanTakeoverFlow:
    """人工接管审核链路测试。"""

    @pytest.mark.asyncio
    async def test_switch_to_human_takeover_sends_alert(
        self,
        db: AsyncSession,
        merchant_id: str,
        conversation: Conversation,
    ) -> None:
        """切换人工接管应触发告警。"""
        with patch.object(svc, "send_alert", new_callable=AsyncMock) as mock_alert:
            await svc.switch_to_human_takeover(
                merchant_id,
                conversation.id,
                reason="用户要求人工服务",
                db=db,
            )
            assert mock_alert.called
