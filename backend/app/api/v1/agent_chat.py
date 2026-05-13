"""Agent 对话 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.agent_chat import (
    AgentChatRequest,
    AgentChatResponse,
    ModelInfo,
    ModelsResponse,
    RagSource,
)
from app.schemas.base import BaseResponse
from agent.llm.base import BaseLLM
from agent.llm.deepseek_llm import DeepSeekLLM
from agent.llm.minimax_llm import MiniMaxLLM
from agent.llm.openai_llm import OpenAILLM
from agent.memory.short_term import ShortTermMemory
from agent.prompts.customer_service import CUSTOMER_SERVICE_PROMPT

router = APIRouter(prefix="/agent", tags=["Agent 对话"])

# Module-level singletons（延迟初始化）
_memory: ShortTermMemory | None = None

# LLM 实例缓存
_llm_cache: dict[str, BaseLLM] = {}


def _get_memory() -> ShortTermMemory:
    """延迟初始化 ShortTermMemory 单例。"""
    global _memory
    if _memory is None:
        _memory = ShortTermMemory()
    return _memory


def _resolve_llm(model: str) -> BaseLLM:
    """根据模型 ID 解析 LLM 实例。"""
    if model in _llm_cache:
        return _llm_cache[model]

    match model:
        case "MiniMax-M2.7":
            llm = MiniMaxLLM()
        case "deepseek-chat":
            llm = DeepSeekLLM()
        case "gpt-4o":
            llm = OpenAILLM()
        case _:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": 40103,
                    "message": f"不支持的模型: {model}，可用模型: MiniMax-M2.7, deepseek-chat, gpt-4o",
                    "data": None,
                },
            )

    _llm_cache[model] = llm
    return llm


@router.post("/chat", response_model=BaseResponse[AgentChatResponse])
async def agent_chat(body: AgentChatRequest) -> BaseResponse[AgentChatResponse]:
    """Agent 对话接口：加载上下文 → LLM 回复 → 保存记忆。"""
    # 1. 解析 LLM
    llm = _resolve_llm(body.model)

    # 2. 加载历史上下文
    context = await _get_memory().get_context(body.conversation_id)

    # 3. 构建提示词（暂不注入 RAG 结果）
    context_text = _format_context(context)
    system_prompt = CUSTOMER_SERVICE_PROMPT.format(
        brand_name="RedFlow",
        system_prompt="你是一个专业的小红书营销助手，帮助商家解答产品和营销相关问题。",
        context=context_text,
        rag_results="暂未接入知识库。",
        user_message=body.message,
        tone="亲切专业",
    )

    # 4. 构建消息列表
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend(context)
    messages.append({"role": "user", "content": body.message})

    # 5. 调用 LLM
    try:
        reply = await llm.chat(messages)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": 40103, "message": str(e), "data": None},
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail={"code": 40102, "message": str(e), "data": None},
        )

    # 6. 保存到短期记忆
    await _get_memory().append_message(body.conversation_id, "user", body.message)
    await _get_memory().append_message(body.conversation_id, "assistant", reply)

    return BaseResponse(
        data=AgentChatResponse(
            reply=reply,
            rag_sources=[],
            conversation_id=body.conversation_id,
            model=body.model,
        )
    )


@router.get("/models", response_model=BaseResponse[ModelsResponse])
async def agent_models() -> BaseResponse[ModelsResponse]:
    """返回可用模型列表及其可用状态。"""
    models = [
        ModelInfo(
            id="MiniMax-M2.7",
            name="MiniMax",
            available=bool(settings.minimax_api_key),
        ),
        ModelInfo(
            id="deepseek-chat",
            name="DeepSeek",
            available=bool(settings.deepseek_api_key),
        ),
        ModelInfo(
            id="gpt-4o",
            name="GPT-4o",
            available=bool(settings.openai_api_key),
        ),
    ]
    return BaseResponse(data=ModelsResponse(models=models))


def _format_context(messages: list[dict]) -> str:
    """格式化历史对话为提示词文本。"""
    if not messages:
        return "无历史对话。"
    lines: list[str] = []
    for m in messages:
        role = "用户" if m.get("role") == "user" else "助手"
        lines.append(f"{role}: {m.get('content', '')}")
    return "\n".join(lines)
