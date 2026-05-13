"""Agent Chat API 集成测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient


def _mock_setup(*, mock_llm=None, mock_memory=None):
    """工具函数：同时 mock _resolve_llm 和 _get_memory。"""
    if mock_llm is None:
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = "测试回复"
    if mock_memory is None:
        mock_memory = AsyncMock()
        mock_memory.get_context.return_value = []
    return (
        patch("app.api.v1.agent_chat._resolve_llm", return_value=mock_llm),
        patch("app.api.v1.agent_chat._get_memory", return_value=mock_memory),
        mock_llm,
        mock_memory,
    )


@pytest.mark.asyncio
async def test_chat_returns_reply() -> None:
    """POST /api/v1/agent/chat 正常流程应返回回复 + conversation_id。"""
    patch_llm, patch_mem, mock_llm, _ = _mock_setup()
    mock_llm.chat.return_value = "你好！根据知识库，这款产品适合油性皮肤。"

    with patch_llm, patch_mem:
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/agent/chat",
                json={
                    "message": "这款产品适合油皮吗？",
                    "conversation_id": str(uuid4()),
                    "model": "MiniMax-M2.7",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["reply"] == mock_llm.chat.return_value
    assert "conversation_id" in data["data"]
    assert data["data"]["model"] == "MiniMax-M2.7"


@pytest.mark.asyncio
async def test_chat_returns_validation_error_for_empty_message() -> None:
    """空消息应返回 422 校验错误。"""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={
                "message": "",
                "conversation_id": str(uuid4()),
                "model": "minimax-abab6.5s",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_returns_validation_error_for_long_message() -> None:
    """超长消息应返回 422 校验错误。"""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={
                "message": "x" * 2001,
                "conversation_id": str(uuid4()),
                "model": "minimax-abab6.5s",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_saves_context_to_memory() -> None:
    """对话完成后应将 user 和 assistant 消息保存到 ShortTermMemory。"""
    patch_llm, patch_mem, mock_llm, mock_memory = _mock_setup()
    mock_llm.chat.return_value = "这是回复"
    conversation_id = str(uuid4())

    with patch_llm, patch_mem:
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/agent/chat",
                json={
                    "message": "你好",
                    "conversation_id": conversation_id,
                    "model": "deepseek-chat",
                },
            )

    assert mock_memory.append_message.call_count == 2
    mock_memory.append_message.assert_any_call(conversation_id, "user", "你好")
    mock_memory.append_message.assert_any_call(
        conversation_id, "assistant", "这是回复"
    )


@pytest.mark.asyncio
async def test_chat_loads_context_from_memory() -> None:
    """对话请求应先从 ShortTermMemory 加载历史上下文。"""
    conversation_id = str(uuid4())
    history = [
        {"role": "user", "content": "上次的问题"},
        {"role": "assistant", "content": "上次的回答"},
    ]
    patch_llm, patch_mem, mock_llm, mock_memory = _mock_setup()
    mock_memory.get_context.return_value = history

    with patch_llm, patch_mem:
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/agent/chat",
                json={
                    "message": "继续",
                    "conversation_id": conversation_id,
                    "model": "MiniMax-M2.7",
                },
            )

    mock_memory.get_context.assert_called_once_with(conversation_id)


@pytest.mark.asyncio
async def test_chat_handles_unknown_model() -> None:
    """无效模型名应返回 400 错误。"""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={
                "message": "你好",
                "conversation_id": str(uuid4()),
                "model": "unknown-model-xyz",
            },
        )

    assert response.status_code == 400
    data = response.json()
    # FastAPI HTTPException(detail=dict) 将 detail 作为响应体
    assert data["detail"]["code"] != 0


@pytest.mark.asyncio
async def test_models_endpoint_returns_available_models() -> None:
    """GET /api/v1/agent/models 应返回可用模型列表。"""
    from app.main import app

    with patch("app.api.v1.agent_chat.settings") as mock_settings:
        mock_settings.minimax_api_key = ""
        mock_settings.deepseek_api_key = "set"
        mock_settings.openai_api_key = "set"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/agent/models")

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    models = data["data"]["models"]
    assert len(models) == 3

    by_id = {m["id"]: m for m in models}
    assert by_id["MiniMax-M2.7"]["available"] is False
    assert by_id["deepseek-chat"]["available"] is True
    assert by_id["gpt-4o"]["available"] is True
