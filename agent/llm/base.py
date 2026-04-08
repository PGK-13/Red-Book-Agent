from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM 抽象接口，支持替换 GPT-4o / DeepSeek / Qwen 等模型。"""

    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str:
        """发送对话请求，返回模型回复文本。"""
        ...

    @abstractmethod
    async def function_call(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        """执行 Function Calling，返回工具调用结果。"""
        ...
