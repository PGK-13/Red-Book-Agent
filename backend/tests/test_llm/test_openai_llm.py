"""OpenAI LLM 适配器单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.llm.base import BaseLLM


class TestOpenAILLMInit:
    """测试 OpenAILLM 初始化行为。"""

    def test_is_base_llm_subclass(self) -> None:
        """OpenAILLM 应是 BaseLLM 的子类。"""
        from agent.llm.openai_llm import OpenAILLM

        assert issubclass(OpenAILLM, BaseLLM)


class TestOpenAILLMChat:
    """测试 OpenAILLM.chat() 方法。"""

    @pytest.mark.asyncio
    async def test_returns_text_on_success(self) -> None:
        """正常调用应返回字符串回复。"""
        from agent.llm.openai_llm import OpenAILLM

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello! How can I help?"}}
            ]
        }

        with (
            patch("agent.llm.openai_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = OpenAILLM()
            result = await llm.chat([{"role": "user", "content": "Hello"}])

            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_raises_when_no_api_key(self) -> None:
        """API Key 未配置时应抛出明确错误。"""
        from agent.llm.openai_llm import OpenAILLM

        with patch("agent.llm.openai_llm.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            mock_settings.openai_model = "gpt-4o"

            llm = OpenAILLM()
            with pytest.raises(ValueError, match="OpenAI API Key"):
                await llm.chat([{"role": "user", "content": "Hello"}])

    @pytest.mark.asyncio
    async def test_handles_http_error(self) -> None:
        """HTTP 错误应抛出 RuntimeError。"""
        from agent.llm.openai_llm import OpenAILLM

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with (
            patch("agent.llm.openai_llm.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            llm = OpenAILLM()
            with pytest.raises(RuntimeError, match="OpenAI API"):
                await llm.chat([{"role": "user", "content": "Hello"}])
