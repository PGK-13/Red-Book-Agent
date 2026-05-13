"""OpenAI LLM 适配器（GPT-4o）。"""

from __future__ import annotations

import httpx

from agent.llm.base import BaseLLM
from app.config import settings


class OpenAILLM(BaseLLM):
    """OpenAI 对话模型实现，默认使用 GPT-4o。"""

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """调用 OpenAI Chat Completions API，返回回复文本。"""
        if not settings.openai_api_key:
            raise ValueError(
                "OpenAI API Key 未配置，请在 .env 中设置 OPENAI_API_KEY"
            )

        temperature = kwargs.get("temperature", 0.7)

        payload = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": temperature,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"OpenAI API 返回错误 ({response.status_code}): {response.text}"
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def function_call(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        """OpenAI Function Calling — 首版暂未实现。"""
        raise NotImplementedError("OpenAI Function Calling 尚未实现")
