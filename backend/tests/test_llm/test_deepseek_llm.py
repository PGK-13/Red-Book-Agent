"""DeepSeek LLM 适配器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.llm.base import BaseLLM


class TestDeepSeekLLMInit:
    """测试 DeepSeekLLM 初始化行为。"""

    def test_is_base_llm_subclass(self) -> None:
        """DeepSeekLLM 应是 BaseLLM 的子类。"""
        from agent.llm.deepseek_llm import DeepSeekLLM

        assert issubclass(DeepSeekLLM, BaseLLM)


class TestDeepSeekLLMChat:
    """测试 DeepSeekLLM.chat() 方法。"""

    @pytest.mark.asyncio
    async def test_returns_text_on_success(self) -> None:
        """正常调用应返回字符串回复。"""
        from agent.llm.deepseek_llm import DeepSeekLLM

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "你好！有什么可以帮你的？"}}
            ]
        }

        with (
            patch("agent.llm.deepseek_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.deepseek_api_key = "test-key"
            mock_settings.deepseek_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = DeepSeekLLM()
            result = await llm.chat([{"role": "user", "content": "你好"}])

            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_raises_when_no_api_key(self) -> None:
        """API Key 未配置时应抛出明确错误。"""
        from agent.llm.deepseek_llm import DeepSeekLLM

        with patch("agent.llm.deepseek_llm.settings") as mock_settings:
            mock_settings.deepseek_api_key = ""
            mock_settings.deepseek_model = "deepseek-chat"

            llm = DeepSeekLLM()
            with pytest.raises(ValueError, match="DeepSeek API Key"):
                await llm.chat([{"role": "user", "content": "你好"}])

    @pytest.mark.asyncio
    async def test_handles_http_error(self) -> None:
        """HTTP 错误应抛出 RuntimeError。"""
        from agent.llm.deepseek_llm import DeepSeekLLM

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with (
            patch("agent.llm.deepseek_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.deepseek_api_key = "test-key"
            mock_settings.deepseek_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = DeepSeekLLM()
            with pytest.raises(RuntimeError, match="DeepSeek API"):
                await llm.chat([{"role": "user", "content": "你好"}])

    @pytest.mark.asyncio
    async def test_sends_correct_request_format(self) -> None:
        """验证发送给 DeepSeek API 的请求体格式正确。"""
        from agent.llm.deepseek_llm import DeepSeekLLM

        last_body: dict = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "测试"}}]
        }

        async def capture_post(url: str, **kwargs) -> MagicMock:
            nonlocal last_body
            last_body = kwargs.get("json", {})
            return mock_response

        with (
            patch("agent.llm.deepseek_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.deepseek_api_key = "test-key"
            mock_settings.deepseek_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=capture_post)
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = DeepSeekLLM()
            await llm.chat(
                [
                    {"role": "system", "content": "你是客服"},
                    {"role": "user", "content": "产品价格？"},
                ],
                temperature=0.3,
            )

            assert last_body["model"] == "deepseek-chat"
            assert last_body["messages"] == [
                {"role": "system", "content": "你是客服"},
                {"role": "user", "content": "产品价格？"},
            ]
            assert last_body["temperature"] == 0.3
