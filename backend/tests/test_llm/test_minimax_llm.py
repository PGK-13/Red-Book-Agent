"""MiniMax LLM 适配器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.llm.base import BaseLLM


class TestMiniMaxLLMInit:
    """测试 MiniMaxLLM 初始化行为。"""

    def test_is_base_llm_subclass(self) -> None:
        """MiniMaxLLM 应是 BaseLLM 的子类。"""
        from agent.llm.minimax_llm import MiniMaxLLM

        assert issubclass(MiniMaxLLM, BaseLLM)

    def test_raises_when_no_api_key(self) -> None:
        """API Key 未配置时初始化不应抛错，调用时才应抛错。"""
        from agent.llm.minimax_llm import MiniMaxLLM

        with patch("agent.llm.minimax_llm.settings") as mock_settings:
            mock_settings.minimax_api_key = ""
            mock_settings.minimax_model = "MiniMax-M2.7"

            llm = MiniMaxLLM()
            assert isinstance(llm, BaseLLM)


class TestMiniMaxLLMChat:
    """测试 MiniMaxLLM.chat() 方法。"""

    @pytest.mark.asyncio
    async def test_returns_text_on_success(self) -> None:
        """正常调用应返回字符串回复。"""
        from agent.llm.minimax_llm import MiniMaxLLM

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "reply": "你好！有什么可以帮你的？",
        }

        with (
            patch("agent.llm.minimax_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.minimax_api_key = "test-key"
            mock_settings.minimax_model = "MiniMax-M2.7"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = MiniMaxLLM()
            result = await llm.chat([{"role": "user", "content": "你好"}])

            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_raises_when_no_api_key_on_chat(self) -> None:
        """API Key 未配置时调用 chat 应抛出明确错误。"""
        from agent.llm.minimax_llm import MiniMaxLLM

        with patch("agent.llm.minimax_llm.settings") as mock_settings:
            mock_settings.minimax_api_key = ""
            mock_settings.minimax_model = "MiniMax-M2.7"

            llm = MiniMaxLLM()
            with pytest.raises(ValueError, match="MiniMax API Key"):
                await llm.chat([{"role": "user", "content": "你好"}])

    @pytest.mark.asyncio
    async def test_handles_http_error(self) -> None:
        """HTTP 错误应抛出 RuntimeError 包含状态码和错误信息。"""
        from agent.llm.minimax_llm import MiniMaxLLM

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with (
            patch("agent.llm.minimax_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.minimax_api_key = "test-key"
            mock_settings.minimax_model = "MiniMax-M2.7"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = MiniMaxLLM()
            with pytest.raises(RuntimeError, match="MiniMax API"):
                await llm.chat([{"role": "user", "content": "你好"}])

    @pytest.mark.asyncio
    async def test_sends_correct_request_format(self) -> None:
        """验证发送给 MiniMax API 的请求体格式正确。"""
        from agent.llm.minimax_llm import MiniMaxLLM

        last_body: dict = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"reply": "测试回复"}

        async def capture_post(url: str, **kwargs) -> MagicMock:
            nonlocal last_body
            last_body = kwargs.get("json", {})
            return mock_response

        with (
            patch("agent.llm.minimax_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.minimax_api_key = "test-key"
            mock_settings.minimax_model = "MiniMax-M2.7"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=capture_post)
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = MiniMaxLLM()
            await llm.chat(
                [
                    {"role": "system", "content": "你是客服"},
                    {"role": "user", "content": "产品多少钱？"},
                ],
                temperature=0.5,
            )

            assert last_body["model"] == "MiniMax-M2.7"
            assert last_body["messages"] == [
                {"role": "system", "content": "你是客服"},
                {"role": "user", "content": "产品多少钱？"},
            ]
            assert last_body["temperature"] == 0.5
