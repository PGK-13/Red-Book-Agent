from langchain_openai import ChatOpenAI

from agent.llm.base import BaseLLM
from app.config import settings


class OpenAILLM(BaseLLM):
    """GPT-4o 实现。"""

    def __init__(self) -> None:
        self._client = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
        )

    async def chat(self, messages: list[dict], **kwargs) -> str:
        # TODO: 实现对话调用
        raise NotImplementedError

    async def function_call(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        # TODO: 实现 Function Calling
        raise NotImplementedError
