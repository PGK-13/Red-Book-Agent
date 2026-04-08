from agent.llm.base import BaseLLM


class DeepSeekLLM(BaseLLM):
    """DeepSeek 实现（备用模型）。"""

    async def chat(self, messages: list[dict], **kwargs) -> str:
        # TODO: 实现 DeepSeek 对话调用
        raise NotImplementedError

    async def function_call(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        # TODO: 实现 DeepSeek Function Calling
        raise NotImplementedError
