"""Agent 对话请求/响应 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """对话请求体。"""

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str = Field(..., min_length=1, max_length=128)
    model: str = Field(default="MiniMax-M2.7", max_length=64)


class RagSource(BaseModel):
    """RAG 检索来源。"""

    content: str
    score: float
    source_doc_id: str | None = None


class AgentChatResponse(BaseModel):
    """对话响应体。"""

    reply: str
    rag_sources: list[RagSource] = []
    conversation_id: str
    model: str


class ModelInfo(BaseModel):
    """可用模型信息。"""

    id: str
    name: str
    available: bool


class ModelsResponse(BaseModel):
    """可用模型列表响应。"""

    models: list[ModelInfo]
