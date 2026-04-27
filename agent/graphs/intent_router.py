"""意图路由 Agent 图 — IntentRouterGraph。

使用 LangGraph 实现评论和私信的意图分类。
评论场景（6类）和私信场景（7类）共用同一 Agent，通过 source_type 参数区分。
输出：intent、confidence、sentiment_score、needs_human_review、review_reason
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.config import settings

logger = logging.getLogger(__name__)


# ── State 定义 ──────────────────────────────────────────────────────────────


@dataclass
class IntentRouterState:
    """意图路由状态机输入/输出状态。"""

    source_type: str = ""  # "comment" or "message"
    content: str = ""  # 原始文本
    ocr_result: str | None = None  # OCR 识别文本（如有）
    merchant_id: str = ""

    # 输出字段（由 classify 节点填充）
    intent: str | None = None
    confidence: float | None = None
    sentiment_score: float | None = None
    needs_human_review: bool = False
    review_reason: str | None = None


# ── LLM 初始化 ───────────────────────────────────────────────────────────────


def _get_llm() -> ChatOpenAI:
    """获取 LLM 实例（GPT-4o）。"""
    return ChatOpenAI(
        model=settings.openai_model or "gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0.3,  # 低温度保证分类稳定性
    )


# ── Prompt 构建 ──────────────────────────────────────────────────────────────


def _build_classification_prompt(state: IntentRouterState) -> str:
    """根据 source_type 构建分类 prompt。"""
    comment_intents = ["ask_price", "complaint", "ask_link", "general_inquiry", "competitor_mention", "other"]
    dm_intents = ["ask_price", "ask_link", "purchase_intent", "complaint", "high_value_bd", "general_inquiry", "other"]

    if state.source_type == "comment":
        intent_list_str = ", ".join(comment_intents)
    else:
        intent_list_str = ", ".join(dm_intents)

    ocr_text = state.ocr_result or "无"
    content = state.content or "无"

    return f"""你是一个小红书评论/私信意图分类助手。

请分析用户输入，返回以下字段（JSON格式）：
{{
  "intent": "意图类别",
  "confidence": 置信度（0.0 ~ 1.0）,
  "sentiment_score": 情绪分数（-1.0 ~ 1.0，负数为负面情绪）
}}

## 评论场景（source=comment）可用意图：
{', '.join(comment_intents)}

## 私信场景（source=message）可用意图：
{', '.join(dm_intents)}

## 分类依据：
- ask_price: 询问价格、优惠、折扣
- complaint: 投诉、负面反馈、强烈不满
- ask_link: 询问链接、二维码、联系方式
- general_inquiry: 一般性咨询
- competitor_mention: 提及竞品（仅评论场景）
- purchase_intent: 明确购买意向（仅私信场景）
- high_value_bd: 高价值商业合作/探店邀约（仅私信场景）
- other: 其他

## 输入信息：
source: {state.source_type}
文本内容：{content}
OCR结果：{ocr_text}

请仔细分析文本内容和OCR结果（如有），给出最准确的分类。只返回JSON，不要有其他内容。"""


# ── 节点定义 ────────────────────────────────────────────────────────────────


async def classify_intent_node(state: IntentRouterState) -> IntentRouterState:
    """意图分类节点 — 调用 GPT-4o 进行分类。

    根据 source_type 构建不同的分类 prompt（评论6类/私信7类）。
    输出：intent、confidence、sentiment_score、needs_human_review、review_reason
    """
    llm = _get_llm()
    prompt = _build_classification_prompt(state)

    try:
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        content_text = response.content if hasattr(response, "content") else str(response)

        # 解析 JSON 输出
        parsed = json.loads(content_text)

        intent = parsed.get("intent", "other")
        confidence = float(parsed.get("confidence", 0.0))
        sentiment_score = float(parsed.get("sentiment_score", 0.0))

        # 判断是否需要人工审核
        needs_review = False
        review_reason = None

        # 评论场景：complaint / competitor_mention / 低置信度 / 强负面情绪
        if state.source_type == "comment":
            if confidence < 0.7:
                needs_review = True
                review_reason = "low_confidence"
            elif sentiment_score < -0.8:
                needs_review = True
                review_reason = "strong_negative"
            elif intent in {"complaint", "competitor_mention"}:
                needs_review = True
                review_reason = f"high_risk_intent_{intent}"

        # 私信场景：complaint / high_value_bd / 低置信度 / 强负面情绪
        else:
            if confidence < 0.7:
                needs_review = True
                review_reason = "low_confidence"
            elif sentiment_score < -0.8:
                needs_review = True
                review_reason = "strong_negative"
            elif intent in {"complaint", "high_value_bd"}:
                needs_review = True
                review_reason = f"high_risk_intent_{intent}"

        return state.model_copy(
            update={
                "intent": intent,
                "confidence": confidence,
                "sentiment_score": sentiment_score,
                "needs_human_review": needs_review,
                "review_reason": review_reason,
            }
        )

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Intent classification parsing failed: {e}, fallback to other")
        return state.model_copy(
            update={
                "intent": "other",
                "confidence": 0.0,
                "sentiment_score": 0.0,
                "needs_human_review": True,
                "review_reason": "parsing_failed",
            }
        )


# ── 图构建 ──────────────────────────────────────────────────────────────────


def build_intent_router_graph() -> StateGraph:
    """构建意图路由状态机图。

    流程：START → classify_intent → END
    简单线性结构，无条件分支。
    """
    graph = StateGraph(IntentRouterState)

    # 添加节点
    graph.add_node("classify_intent", classify_intent_node)

    # 设置入口和结束
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", END)

    return graph


# ── 对外接口 ────────────────────────────────────────────────────────────────


class IntentRouterGraph:
    """意图路由 Agent 图。

    使用方式：
    ```python
    agent = IntentRouterGraph()
    result = await agent.classify(
        source_type="comment",
        content="这个多少钱？",
        ocr_result=None,
        merchant_id="xxx",
    )
    ```
    """

    def __init__(self) -> None:
        self._graph = build_intent_router_graph()
        self._compiled = self._graph.compile()

    async def classify(
        self,
        source_type: str,
        content: str,
        ocr_result: str | None,
        merchant_id: str,
    ) -> IntentRouterState:
        """执行意图分类。

        Args:
            source_type: 来源类型，"comment" 或 "message"。
            content: 原始文本内容。
            ocr_result: OCR 识别文本（如评论含图片）。
            merchant_id: 商家 ID。

        Returns:
            IntentRouterState，包含分类结果。
        """
        initial_state = IntentRouterState(
            source_type=source_type,
            content=content,
            ocr_result=ocr_result,
            merchant_id=merchant_id,
        )

        result = await self._compiled.ainvoke(initial_state)
        return result


# 预编译实例（供复用）
_intent_router_graph: IntentRouterGraph | None = None


def get_intent_router_graph() -> IntentRouterGraph:
    """获取单例 IntentRouterGraph 实例。"""
    global _intent_router_graph
    if _intent_router_graph is None:
        _intent_router_graph = IntentRouterGraph()
    return _intent_router_graph