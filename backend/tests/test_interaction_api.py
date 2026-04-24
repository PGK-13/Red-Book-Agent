"""模块 D API 路由单元测试。

测试范围：
- 监测笔记 CRUD 参数校验（400/422）
- 评论回复字数校验（15-80 字）
- HITL 批量审核上限（≤20 条）
- 响应格式符合 BaseResponse 规范
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ─────────────────────────────────────────────────────────────────────────────
# 监测笔记 CRUD
# ─────────────────────────────────────────────────────────────────────────────


class TestMonitoredNoteAPI:
    """监测笔记 API 测试。"""

    @pytest.mark.asyncio
    async def test_create_monitored_note(self, client: AsyncClient) -> None:
        """正常创建监测笔记。"""
        merchant_id = str(uuid4())
        account_id = str(uuid4())
        payload = {
            "account_id": str(account_id),
            "xhs_note_id": "note_api_001",
            "note_title": "API 测试笔记",
            "check_interval_seconds": 60,
            "batch_size": 3,
        }
        with patch("app.dependencies.get_current_merchant", return_value=merchant_id):
            resp = await client.post(
                "/api/v1/interaction/monitored-notes",
                json=payload,
                headers={"x-merchant-id": merchant_id},
            )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["xhs_note_id"] == "note_api_001"

    @pytest.mark.asyncio
    async def test_create_note_invalid_interval(
        self,
        client: AsyncClient,
    ) -> None:
        """check_interval_seconds 超出范围应返回 422。"""
        payload = {
            "account_id": str(uuid4()),
            "xhs_note_id": "note_bad_interval",
            "note_title": "测试",
            "check_interval_seconds": 10,  # < 30
        }
        resp = await client.post("/api/v1/interaction/monitored-notes", json=payload)
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_list_monitored_notes(self, client: AsyncClient) -> None:
        """GET 返回列表。"""
        resp = await client.get("/api/v1/interaction/monitored-notes")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["code"] == 0
        assert "data" in data

    @pytest.mark.asyncio
    async def test_update_monitored_note_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """更新不存在的笔记返回 404。"""
        payload = {"is_active": False}
        resp = await client.put(
            f"/api/v1/interaction/monitored-notes/{uuid4()}",
            json=payload,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_monitored_note(self, client: AsyncClient) -> None:
        """删除笔记。"""
        # 先创建
        create_payload = {
            "account_id": str(uuid4()),
            "xhs_note_id": "note_del_001",
            "note_title": "待删除",
        }
        resp = await client.post(
            "/api/v1/interaction/monitored-notes",
            json=create_payload,
        )
        note_id = resp.json()["data"]["id"]

        # 再删除
        resp = await client.delete(
            f"/api/v1/interaction/monitored-notes/{note_id}",
        )
        assert resp.status_code == status.HTTP_200_OK


# ─────────────────────────────────────────────────────────────────────────────
# 评论回复字数校验
# ─────────────────────────────────────────────────────────────────────────────


class TestCommentReplyValidation:
    """评论回复字数校验（15-80 字）。"""

    @pytest.mark.asyncio
    async def test_reply_too_short(self, client: AsyncClient) -> None:
        """回复少于 15 字应返回 422。"""
        payload = {"reply_content": "太短了"}
        resp = await client.post(
            f"/api/v1/interaction/comments/{uuid4()}/reply",
            json=payload,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_reply_too_long(self, client: AsyncClient) -> None:
        """回复超过 80 字应返回 422。"""
        payload = {"reply_content": "这" * 81}
        resp = await client.post(
            f"/api/v1/interaction/comments/{uuid4()}/reply",
            json=payload,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ─────────────────────────────────────────────────────────────────────────────
# HITL 批量审核
# ─────────────────────────────────────────────────────────────────────────────


class TestHITLBatchApprove:
    """HITL 批量审核上限测试（≤20 条）。"""

    @pytest.mark.asyncio
    async def test_batch_approve_exceeds_limit(self, client: AsyncClient) -> None:
        """批量审核超过 20 条应返回 422。"""
        payload = {
            "queue_ids": [str(uuid4()) for _ in range(21)],
            "reviewer_id": str(uuid4()),
        }
        resp = await client.post(
            "/api/v1/interaction/hitl/batch-approve",
            json=payload,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_batch_approve_at_limit(self, client: AsyncClient) -> None:
        """恰好 20 条应通过。"""
        payload = {
            "queue_ids": [str(uuid4()) for _ in range(20)],
            "reviewer_id": str(uuid4()),
        }
        with patch("app.api.v1.interaction.svc.get_hitl_queue_item", new_callable=AsyncMock, return_value=None):
            resp = await client.post(
                "/api/v1/interaction/hitl/batch-approve",
                json=payload,
            )
        # 返回 404（ID 不存在）或 200（找到），但不应是 422
        assert resp.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY


# ─────────────────────────────────────────────────────────────────────────────
# BaseResponse 格式
# ─────────────────────────────────────────────────────────────────────────────


class TestBaseResponseFormat:
    """响应格式符合 {code, message, data} 规范。"""

    @pytest.mark.asyncio
    async def test_monitored_notes_response_format(self, client: AsyncClient) -> None:
        """监测笔记列表响应格式正确。"""
        resp = await client.get("/api/v1/interaction/monitored-notes")
        data = resp.json()
        assert "code" in data
        assert "message" in data
        assert "data" in data
        assert data["code"] == 0

    @pytest.mark.asyncio
    async def test_hitl_queue_response_format(self, client: AsyncClient) -> None:
        """HITL 队列响应格式正确。"""
        resp = await client.get("/api/v1/interaction/hitl/queue")
        data = resp.json()
        assert "code" in data
        assert "message" in data
        assert "data" in data

    @pytest.mark.asyncio
    async def test_error_response_has_code(self, client: AsyncClient) -> None:
        """错误响应也有 code 字段。"""
        resp = await client.get(
            f"/api/v1/interaction/comments/{uuid4()}",
        )
        # 404 时 code 非 0
        data = resp.json()
        assert "code" in data
