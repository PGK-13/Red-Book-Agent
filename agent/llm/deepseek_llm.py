"""DeepSeek LLM 适配器（deepseek-chat）。"""

from __future__ import annotations

import httpx

from agent.llm.base import BaseLLM
from app.config import settings


class DeepSeekLLM(BaseLLM):
    """DeepSeek 对话模型实现，默认使用 deepseek-chat。"""

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """调用 DeepSeek API（OpenAI 兼容），返回回复文本。"""
        if not settings.deepseek_api_key:
            raise ValueError(
                "DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY"
            )

        temperature = kwargs.get("temperature", 0.7)

        payload = {
            "model": settings.deepseek_model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"DeepSeek API 返回错误 ({response.status_code}): {response.text}"
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def function_call(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        """DeepSeek Function Calling — 首版暂未实现。"""
        raise NotImplementedError("DeepSeek Function Calling 尚未实现")
