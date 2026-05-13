"""MiniMax LLM 适配器（MiniMax-M2.7）。"""

from __future__ import annotations

import httpx

from agent.llm.base import BaseLLM
from app.config import settings


class MiniMaxLLM(BaseLLM):
    """MiniMax 对话模型实现，默认使用 MiniMax-M2.7。"""

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """调用 MiniMax ChatCompletion v2 API，返回回复文本。"""
        if not settings.minimax_api_key:
            raise ValueError(
                "MiniMax API Key 未配置，请在 .env 中设置 MINIMAX_API_KEY"
            )

        temperature = kwargs.get("temperature", 0.7)

        payload = {
            "model": settings.minimax_model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.minimax.chat/v1/text/chatcompletion_v2",
                headers={
                    "Authorization": f"Bearer {settings.minimax_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"MiniMax API 返回错误 ({response.status_code}): {response.text}"
            )

        data = response.json()

        # 检查业务错误（base_resp.status_code != 0）
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code", 0) != 0:
            raise RuntimeError(
                f"MiniMax API 错误 ({base_resp['status_code']}): "
                f"{base_resp.get('status_msg', '未知错误')}"
            )

        # 解析回复：优先 reply 字段，其次 choices
        if reply := data.get("reply"):
            return reply

        choices = data.get("choices")
        if choices:
            if msg := choices[0].get("messages", [None])[0]:
                return msg["content"]
            if msg := choices[0].get("message"):
                return msg["content"]

        raise RuntimeError(
            f"MiniMax API 返回格式异常: {str(data)[:500]}"
        )

    async def function_call(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        """MiniMax Function Calling — 首版暂未实现。"""
        raise NotImplementedError("MiniMax Function Calling 尚未实现")
