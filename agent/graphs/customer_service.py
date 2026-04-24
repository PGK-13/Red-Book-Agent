"""实时客服 Agent 图（D5）— CustomerServiceGraph。

节点编排：check_mode → check_captcha → classify_intent → check_human_review
        → check_online_hours → load_memory → rag_retrieve → generate_reply
        → risk_scan → humanized_send → pending_queue

关键约束：端到端 ≤5s（从接收消息到回复发送）。
连接中断时通过 Redis session:pending:{conversation_id} 队列补发。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

# ── 常量定义 ────────────────────────────────────────────────────────────────

_CONFIDENCE_THRESHOLD = 0.7
_STRONG_NEGATIVE_THRESHOLD = -0.8
_MAX_CONTEXT_ROUNDS = 10  # 最近 10 轮上下文


# ── State 定义 ──────────────────────────────────────────────────────────────


@dataclass
class CustomerServiceState:
    """实时客服状态机状态。"""

    # 输入字段
    conversation_id: str = ""
    merchant_id: str = ""
    account_id: str = ""
    xhs_user_id: str = ""
    user_message: str = ""  # 用户发送的消息
    mode: str = "auto"  # auto / human_takeover / pending
    db: object | None = None  # 数据库会话（由调用方注入）

    # 中间状态（各节点填充）
    is_captcha_blocked: bool = False
    intent: str | None = None
    confidence: float | None = None
    sentiment_score: float | None = None
    needs_human_review: bool = False
    review_reason: str | None = None
    is_within_online_hours: bool = True

    # 记忆检索
    context_messages: list[dict] = field(default_factory=list)  # 历史消息
    long_term_memory: dict | None = None  # 长期记忆

    # RAG 检索结果
    rag_results: list[str] = field(default_factory=list)

    # 生成回复
    generated_reply: str | None = None

    # 风控结果
    risk_scan_passed: bool = False
    risk_hit_keywords: list[str] = field(default_factory=list)

    # 最终输出
    final_reply: str | None = None
    send_success: bool = False
    error_message: str | None = None

    # pending 队列（连接中断时）
    pending_queue_key: str = ""


# ── LLM 初始化 ───────────────────────────────────────────────────────────────


def _get_llm() -> ChatOpenAI:
    """获取 LLM 实例（GPT-4o）。"""
    return ChatOpenAI(
        model=settings.openai_model or "gpt-4o",
        api_key=settings.openai_api_key,
        temperature=0.7,
    )


# ── 节点定义 ────────────────────────────────────────────────────────────────


async def check_mode_node(state: CustomerServiceState) -> CustomerServiceState:
    """检查会话模式。

    若为 human_takeover，直接跳过自动回复。
    """
    if state.mode == "human_takeover":
        logger.info(f"Conversation {state.conversation_id} in human_takeover mode, skipping auto reply")
        state.final_reply = None
        state.send_success = False
    return state


async def check_captcha_node(state: CustomerServiceState) -> CustomerServiceState:
    """检查 Captcha 阻断标志。

    调用 InteractionService.is_captcha_blocked() 检查 Redis 标记。
    """
    from app.services import interaction_service as svc

    try:
        blocked = await svc.is_captcha_blocked(state.account_id)
        if blocked:
            logger.warning(f"Account {state.account_id} is captcha blocked")
            state.is_captcha_blocked = True
            state.final_reply = None
            state.send_success = False
        else:
            state.is_captcha_blocked = False
    except Exception as e:
        logger.error(f"Captcha check failed: {e}")
        state.is_captcha_blocked = False

    return state


async def classify_intent_node(state: CustomerServiceState) -> CustomerServiceState:
    """意图分类节点。

    调用 IntentRouterGraph 对用户消息进行意图分类（7类 DM 意图）。
    """
    from agent.graphs.intent_router import get_intent_router_graph

    try:
        agent = get_intent_router_graph()
        result = await agent.classify(
            source_type="message",
            content=state.user_message,
            ocr_result=None,
            merchant_id=state.merchant_id,
        )

        state.intent = result.intent
        state.confidence = result.confidence
        state.sentiment_score = result.sentiment_score
        state.needs_human_review = result.needs_human_review
        state.review_reason = result.review_reason

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        state.intent = "other"
        state.confidence = 0.0
        state.sentiment_score = 0.0
        state.needs_human_review = True
        state.review_reason = "classification_error"

    return state


async def check_human_review_node(state: CustomerServiceState) -> CustomerServiceState:
    """检查是否需要人工审核。

    若 needs_human_review 为 True，加入 HITL 审核队列并跳过自动回复。
    """
    if state.needs_human_review:
        logger.info(f"Conversation {state.conversation_id} needs human review, reason: {state.review_reason}")
        state.final_reply = None
        state.send_success = False

        # 写入 HITL 队列
        if state.db is not None and state.conversation_id:
            from app.services import interaction_service as svc

            try:
                await svc.enqueue_hitl(
                    merchant_id=state.merchant_id,
                    conversation_id=state.conversation_id,
                    comment_id=None,
                    trigger_reason=state.review_reason or "low_confidence",
                    original_content=state.user_message,
                    suggested_reply=None,
                    db=state.db,
                )
            except Exception as e:
                logger.error(f"Failed to enqueue HITL: {e}")

    return state


async def check_online_hours_node(state: CustomerServiceState) -> CustomerServiceState:
    """检查在线时段。

    若当前不在在线时段内，返回"稍后为您解答"延迟回复。
    """
    within = True

    if state.db is not None:
        from app.services import interaction_service as svc

        try:
            within = await svc.is_within_online_hours(state.account_id, state.db)
        except Exception as e:
            logger.error(f"Online hours check failed: {e}")
            within = True  # 故障时默认在线，避免误拦截
    else:
        # 无 db 时默认在线
        pass

    if not within:
        logger.info(f"Outside online hours for account {state.account_id}")
        state.is_within_online_hours = False
        state.final_reply = "您好，当前非在线时段，我们将在上班后尽快回复您～"
        state.send_success = False
    else:
        state.is_within_online_hours = True

    return state


async def load_memory_node(state: CustomerServiceState) -> CustomerServiceState:
    """加载会话记忆。

    从 Redis 读取短期上下文（最近 N 条消息）和长期记忆（用户偏好）。
    """
    try:
        from app.core.rate_limiter import get_redis

        redis = await get_redis()

        # 加载短期上下文
        ctx_key = f"session:context:{state.conversation_id}"
        ctx_data = await redis.get(ctx_key)
        if ctx_data:
            state.context_messages = json.loads(ctx_data)
        else:
            state.context_messages = []

        # 加载长期记忆
        mem_key = f"session:memory:{state.xhs_user_id}"
        mem_data = await redis.get(mem_key)
        if mem_data:
            state.long_term_memory = json.loads(mem_data)
        else:
            state.long_term_memory = None

    except Exception as e:
        logger.warning(f"Failed to load memory: {e}")
        state.context_messages = []
        state.long_term_memory = None

    return state


async def rag_retrieve_node(state: CustomerServiceState) -> CustomerServiceState:
    """RAG 检索产品知识。

    根据意图和用户消息检索相关产品知识，供生成回复使用。
    """
    try:
        from agent.tools.rag_retrieval import hybrid_search

        query = state.user_message
        if state.intent:
            query = f"{state.intent} {query}"

        results = await hybrid_search(
            query=query,
            account_id=state.account_id,
            top_k=3,
        )

        state.rag_results = [r["content"] for r in results]

    except (ImportError, NotImplementedError):
        # rag_retrieval.py 尚未实现，跳过 RAG 检索
        logger.debug("RAG retrieval not available, skipping")
        state.rag_results = []
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        state.rag_results = []

    return state


async def generate_reply_node(state: CustomerServiceState) -> CustomerServiceState:
    """生成回复内容。

    根据上下文、RAG 检索结果和客服 prompt 生成最终回复。
    """
    # 构建上下文
    context_lines = []
    for msg in state.context_messages[-_MAX_CONTEXT_ROUNDS:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        context_lines.append(f"{role}: {content}")
    context_str = "\n".join(context_lines) if context_lines else "（暂无历史记录）"

    rag_str = "\n".join(state.rag_results) if state.rag_results else "（暂无相关产品知识）"

    prompt = f"""你是品牌的小红书客服助手。

历史对话：
{context_str}

相关产品知识：
{rag_str}

用户消息：{state.user_message}

请用专业、友好的语气回复，回复长度控制在 100~200 字。
不得包含违禁词、竞品名称。若无法回答，请说"稍后为您解答"。

请直接返回回复内容，不要有其他内容。"""

    try:
        llm = _get_llm()
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        state.generated_reply = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        state.generated_reply = None

    return state


async def risk_scan_node(state: CustomerServiceState) -> CustomerServiceState:
    """风控扫描。

    对生成的回复内容调用 RiskService.scan_output() 进行敏感词和风险检测。
    """
    if not state.generated_reply:
        state.risk_scan_passed = False
        return state

    try:
        from agent.tools.risk_scan import scan_content

        result = await scan_content(
            content=state.generated_reply,
            merchant_id=state.merchant_id,
            account_id=state.account_id,
        )

        state.risk_scan_passed = result.passed
        state.risk_hit_keywords = result.hit_keywords

        if not result.passed:
            logger.warning(
                f"Risk scan failed for conversation {state.conversation_id}: "
                f"keywords={result.hit_keywords}, suggestion={result.suggestion}"
            )
            state.final_reply = None
            state.send_success = False

    except Exception as e:
        logger.error(f"Risk scan failed: {e}")
        # 风控异常时应阻断发送，而非放行
        state.risk_scan_passed = False
        state.risk_hit_keywords = []

    return state


async def humanized_send_node(state: CustomerServiceState) -> CustomerServiceState:
    """人性化发送。

    若风控通过，调用 Playwright RPA 发送回复，注入人类化延迟。
    """
    if not state.risk_scan_passed or not state.generated_reply:
        state.send_success = False
        state.final_reply = None
        return state

    try:
        from agent.tools.playwright_rpa_base import humanized_delay as rpa_delay

        # 注入人类化延迟
        delay_seconds = rpa_delay(min_seconds=3.0, max_seconds=15.0)
        await asyncio.sleep(delay_seconds)

        from agent.tools.playwright_dm_sender import send_dm

        # 获取账号 Cookie（如有 db session）
        cookie = None
        proxy_url = None
        if state.db is not None:
            try:
                from app.models.account import Account
                from app.core.security import decrypt
                from sqlalchemy import select

                stmt = select(Account).where(Account.id == state.account_id)
                result = await state.db.execute(stmt)
                account = result.scalar_one_or_none()
                if account:
                    if hasattr(account, "cookie_enc") and account.cookie_enc:
                        cookie = decrypt(account.cookie_enc)
                    if hasattr(account, "proxy_url_enc") and account.proxy_url_enc:
                        proxy_url = decrypt(account.proxy_url_enc)
            except Exception as e:
                logger.warning(f"Failed to load account credentials: {e}")

        success, error = await send_dm(
            account_id=state.account_id,
            xhs_user_id=state.xhs_user_id,
            content=state.generated_reply,
            cookie=cookie,
            proxy_url=proxy_url,
        )

        if success:
            state.send_success = True
            state.final_reply = state.generated_reply

            # 写入消息记录
            if state.db is not None:
                from app.services import interaction_service as svc

                await svc.append_message(
                    conversation_id=state.conversation_id,
                    role="assistant",
                    content=state.generated_reply,
                    db=state.db,
                    intent=state.intent,
                    confidence=state.confidence,
                )
        else:
            logger.warning(f"DM send failed: {error}")
            state.send_success = False
            state.final_reply = None
            state.error_message = error

    except Exception as e:
        logger.error(f"Humanized send failed: {e}")
        state.send_success = False
        state.final_reply = None
        state.error_message = str(e)

    return state


async def pending_queue_node(state: CustomerServiceState) -> CustomerServiceState:
    """Pending 队列处理。

    若发送失败或需要人工审核，将消息写入 Redis pending 队列等待重试。
    """
    if state.final_reply is None and state.user_message:
        try:
            from app.core.rate_limiter import get_redis

            redis = await get_redis()
            queue_key = f"session:pending:{state.conversation_id}"
            payload = {
                "user_message": state.user_message,
                "generated_reply": state.generated_reply,
                "intent": state.intent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await redis.rpush(queue_key, json.dumps(payload))
            state.pending_queue_key = queue_key
            logger.info(f"Message added to pending queue: {queue_key}")

        except Exception as e:
            logger.error(f"Failed to write pending queue: {e}")
    else:
        state.pending_queue_key = ""

    return state


# ── 图构建 ──────────────────────────────────────────────────────────────────


def build_customer_service_graph() -> StateGraph:
    """构建实时客服状态机图。

    流程：
        START → check_mode → check_captcha → classify_intent
            → check_human_review → check_online_hours → load_memory
            → rag_retrieve → generate_reply → risk_scan → humanized_send
            → pending_queue → END

    条件分支：
    - check_mode: human_takeover → 直接 END
    - check_captcha: blocked → 直接 END
    - check_human_review: needs_review → 直接 END
    - check_online_hours: outside_hours → 直接 END
    """
    graph = StateGraph(CustomerServiceState)

    # 添加节点
    graph.add_node("check_mode", check_mode_node)
    graph.add_node("check_captcha", check_captcha_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("check_human_review", check_human_review_node)
    graph.add_node("check_online_hours", check_online_hours_node)
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("rag_retrieve", rag_retrieve_node)
    graph.add_node("generate_reply", generate_reply_node)
    graph.add_node("risk_scan", risk_scan_node)
    graph.add_node("humanized_send", humanized_send_node)
    graph.add_node("pending_queue", pending_queue_node)

    # 设置入口
    graph.add_edge(START, "check_mode")

    # check_mode 条件分支
    def mode_router(state: CustomerServiceState) -> str:
        if state.mode == "human_takeover":
            return "END"
        return "check_captcha"

    graph.add_conditional_edges("check_mode", mode_router)

    # check_captcha 条件分支
    def captcha_router(state: CustomerServiceState) -> str:
        if state.is_captcha_blocked:
            return "END"
        return "classify_intent"

    graph.add_conditional_edges("check_captcha", captcha_router)

    # check_human_review 条件分支
    def review_router(state: CustomerServiceState) -> str:
        if state.needs_human_review:
            return "END"
        return "check_online_hours"

    graph.add_conditional_edges("check_human_review", review_router)

    # check_online_hours 条件分支
    def online_hours_router(state: CustomerServiceState) -> str:
        if not state.is_within_online_hours:
            return "END"
        return "load_memory"

    graph.add_conditional_edges("check_online_hours", online_hours_router)

    # 线性流程
    graph.add_edge("classify_intent", "check_human_review")
    graph.add_edge("load_memory", "rag_retrieve")
    graph.add_edge("rag_retrieve", "generate_reply")
    graph.add_edge("generate_reply", "risk_scan")
    graph.add_edge("risk_scan", "humanized_send")
    graph.add_edge("humanized_send", "pending_queue")
    graph.add_edge("pending_queue", END)

    return graph


# ── 对外接口 ────────────────────────────────────────────────────────────────


class CustomerServiceGraph:
    """实时客服 Agent 图。

    使用方式：
    ```python
    agent = CustomerServiceGraph()
    result = await agent.reply(
        conversation_id="xxx",
        merchant_id="xxx",
        account_id="xxx",
        xhs_user_id="xxx",
        user_message="这个多少钱？",
        mode="auto",
        db=some_db_session,
    )
    ```
    """

    def __init__(self) -> None:
        self._graph = build_customer_service_graph()
        self._compiled = self._graph.compile()

    async def reply(
        self,
        conversation_id: str,
        merchant_id: str,
        account_id: str,
        xhs_user_id: str,
        user_message: str,
        mode: str = "auto",
        db: AsyncSession | None = None,
    ) -> CustomerServiceState:
        """执行实时客服流程。

        Args:
            conversation_id: 会话 ID。
            merchant_id: 商家 ID。
            account_id: 商家子账号 ID。
            xhs_user_id: 小红书用户 ID。
            user_message: 用户发送的消息。
            mode: 会话模式（auto/human_takeover/pending）。
            db: 数据库会话（可选，用于持久化操作）。

        Returns:
            CustomerServiceState，包含最终回复和发送状态。
        """
        initial_state = CustomerServiceState(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            account_id=account_id,
            xhs_user_id=xhs_user_id,
            user_message=user_message,
            mode=mode,
            db=db,
        )

        result = await self._compiled.ainvoke(initial_state)
        return result


# 预编译实例
_customer_service_graph: CustomerServiceGraph | None = None


def get_customer_service_graph() -> CustomerServiceGraph:
    """获取单例 CustomerServiceGraph 实例。"""
    global _customer_service_graph
    if _customer_service_graph is None:
        _customer_service_graph = CustomerServiceGraph()
    return _customer_service_graph