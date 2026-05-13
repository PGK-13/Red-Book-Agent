# Implementation Plan: Agent 对话系统

## Overview

基于现有项目骨架，按分层架构逐步实现 Agent 对话功能：LLM 适配层 → RAG 检索工具 → API Schema → API 路由 → 前端导航 → 前端对话界面。每一步都在前一步基础上构建，确保端到端可用。

## Tasks

- [ ] 1. 实现 MiniMax LLM 适配器
  - [ ] 1.1 创建 `agent/llm/minimax_llm.py`，实现 `MiniMaxLLM(BaseLLM)` 类
    - `__init__` 从 settings 读取 `minimax_api_key` 和 `minimax_model`（默认 abab6.5s-chat）
    - `chat(messages, **kwargs)` 调用 MiniMax API，将 dict 消息列表转换为 MiniMax 格式，返回回复文本
    - `function_call()` 首版可留空（Agent Chat 暂不需要 function calling）
    - 错误处理：API Key 未配置返回明确错误，HTTP 错误返回状态码 + 原因
    - _Requirements: AG3.1, AG3.4_
  - [ ] 1.2 在 `backend/app/config.py` 新增 MiniMax 配置项
    - `minimax_api_key: str = ""`
    - `minimax_model: str = "abab6.5s-chat"`
    - _Requirements: AG3.1_

- [ ] 2. 完善 DeepSeek LLM 适配器
  - [ ] 2.1 在 `agent/llm/deepseek_llm.py` 中实现 `chat()` 方法（替换 NotImplementedError）
    - 已有 `__init__` stub，配置了 `ChatDeepSeek`（langchain 社区包）
    - `chat(messages, **kwargs)` → 转换消息 → `self._client.ainvoke()` → 返回文本
    - _Requirements: AG3.1, AG3.4_
  - [ ] 2.2 在 `backend/app/config.py` 新增 DeepSeek 配置项
    - `deepseek_api_key: str = ""`
    - `deepseek_model: str = "deepseek-chat"`
    - _Requirements: AG3.1_

- [ ] 3. 完善 OpenAI LLM 适配器
  - [ ] 3.1 在 `agent/llm/openai_llm.py` 中实现 `chat()` 方法（替换 NotImplementedError）
    - 已有 `__init__` 和 `ChatOpenAI` 实例
    - 转换消息格式 → `self._client.ainvoke()` → 返回文本
    - _Requirements: AG3.1, AG3.4_

- [ ] 4. 实现 RAG 检索工具
  - [ ] 4.1 在 `agent/tools/rag_retrieval.py` 中实现 `RAGRetrievalTool` 类（替换 TODO stub）
    - `__init__` → 初始化 `AsyncQdrantClient` + `OpenAIEmbeddings`
    - `search(query, collection_name="knowledge_chunks")` → embedding → Qdrant search → 过滤 score < 0.6 → 返回 Top-5
    - Collection 不存在时返回空列表，不抛异常
    - 返回格式：`[{ "content": str, "score": float, "source_doc_id": str|None }]`
    - _Requirements: AG4.1, AG4.3, B3.1-B3.3_

- [ ] 5. 创建 Agent Chat Schema
  - [ ] 5.1 创建 `backend/app/schemas/agent_chat.py`
    - `AgentChatRequest`：message, conversation_id, model
    - `AgentChatResponse`：reply, rag_sources, conversation_id, model, tokens_used
    - `ModelInfo`：id, name, available
    - `ModelsResponse`：models
    - `RagSource`：content, score, source_doc_id
    - _Requirements: AG3.5, AG4.2_

- [ ] 6. 实现 Agent Chat API 路由
  - [ ] 6.1 创建 `backend/app/api/v1/agent_chat.py`
    - `GET /agent/models` → 返回可用模型列表（检查各模型 API Key 是否配置）
    - `POST /agent/chat` → 完整对话流程：
      1. 校验参数（message/conversation_id/model）
      2. 从 ShortTermMemory 加载上下文
      3. 调用 RAGRetrievalTool.search()
      4. 格式化提示词（复用 `agent/prompts/customer_service.py` 模板）
      5. 根据 model 选择 LLM，调用 chat()
      6. 保存 user/assistant 消息到 ShortTermMemory
      7. 返回 AgentChatResponse
    - 使用 module-level singleton：_memory, _rag, _llm_map
    - 错误处理：捕获异常，返回对应错误码（40101-40104）
    - 注入 `CurrentMerchantId` 依赖
    - _Requirements: AG2.5, AG3.5, AG4.1, AG4.2, AG5.1, AG5.2_
  - [ ] 6.2 在 `backend/app/main.py` 注册 agent_chat router
    - `from app.api.v1 import agent_chat`
    - `app.include_router(agent_chat.router, prefix="/api/v1")`
    - _Requirements: AG3.5_

- [ ] 7. Checkpoint — 后端端到端可用
  - 启动后端，用 curl 测试 POST /api/v1/agent/chat
  - 测试模型切换（model=minimax-abab6.5s / deepseek-chat / gpt-4o）
  - 测试 RAG 降级（无知识库时 rag_sources=[]）
  - 测试错误处理（无效 model 参数）
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. 前端：侧边栏导航入口
  - [ ] 8.1 在 `frontend/components/Sidebar.tsx` 的 `navItems` 数组中新增 "Agent 对话" 项
    - href: "/agent-chat"
    - label: "Agent 对话"
    - icon: 聊天气泡 SVG（与"互动管理"的多人群聊图标区分，使用单聊样式）
    - 位置：在"风控管理"之后
    - _Requirements: AG1.1, AG1.2, AG1.3_
  - [ ] 8.2 在 `frontend/components/TopNav.tsx` 的 `titleMap` 中新增
    - `"/agent-chat": "Agent 对话"`
    - _Requirements: AG1.2_

- [ ] 9. 前端：对话界面
  - [ ] 9.1 创建 `frontend/app/(dashboard)/agent-chat/page.tsx`（client component）
    - 状态管理：messages, input, isLoading, conversationId, selectedModel
    - conversationId 从 localStorage 读取/生成，页面刷新保持
    - 空状态引导 UI（聊天气泡图标 + 提示文字）
    - 消息列表渲染：用户消息右对齐粉色气泡，AI 回复左对齐灰色气泡
    - RAG 来源展示：AI 回复气泡下方折叠面板，显示内容摘要 + 相关度百分比
    - 加载状态：三个跳动圆点动画
    - 输入区：输入框 + 发送按钮，Enter 发送，Shift+Enter 换行
    - 自动滚动到最新消息
    - 错误处理：网络错误/API 错误展示红色提示气泡
    - _Requirements: AG2.1-AG2.8, AG4.2, AG5.3_
  - [ ] 9.2 实现模型选择器
    - 页面挂载时调用 `GET /api/v1/agent/models` 获取模型列表
    - 下拉菜单展示模型名称 + 可用状态（绿色圆点 / 灰色）
    - 默认选中 MiniMax
    - 切换模型后更新 selectedModel，不清空历史消息
    - _Requirements: AG3.2, AG3.3_
  - [ ] 9.3 实现"新对话"功能
    - 按钮位于页面顶部标题栏右侧
    - 点击生成新 conversationId → 更新 localStorage → 清空 messages
    - _Requirements: AG5.3, AG5.4_

- [ ] 10. Checkpoint — 前端端到端可用
  - 启动前端，访问 /agent-chat
  - 验证侧边栏高亮
  - 发送消息 → 验证回复展示 → 验证 RAG 来源展示
  - 切换模型 → 发送消息 → 验证使用新模型
  - 刷新页面 → 验证对话保持
  - 新对话 → 验证消息清空

- [ ] 11. 测试
  - [ ] 11.1 编写 LLM 适配器单元测试
    - 测试各 LLM 实现的 chat() 方法（mock API 响应）
    - 测试 API Key 未配置时的错误处理
    - 测试消息格式转换正确性
    - 在 `backend/tests/test_llm_adapters.py` 中实现
    - _Requirements: AG3.4, AG3.5_
  - [ ] 11.2 编写 RAG 检索工具单元测试
    - 测试正常检索流程（mock Qdrant 响应）
    - 测试相似度阈值过滤
    - 测试 Collection 不存在时的降级处理
    - 在 `backend/tests/test_rag_retrieval.py` 中实现
    - _Requirements: AG4.1, AG4.3_
  - [ ] 11.3 编写 Agent Chat API 集成测试
    - 测试 POST /api/v1/agent/chat 正常流程
    - 测试参数校验（空 message、无效 model）
    - 测试 RAG 降级（无知识库时仍返回回复）
    - 测试上下文维护（多轮对话）
    - 在 `backend/tests/test_agent_chat_api.py` 中实现
    - _Requirements: AG2.5, AG4.2, AG5.1, AG5.2_
  - [ ]* 11.4 编写属性测试：上下文窗口截断
    - **Property: Context window truncation at 10 turns**
    - **Validates: Requirements AG5.1**
    - Hypothesis 生成 11+ 轮对话，验证上下文只保留最近 10 轮
    - 在 `backend/tests/test_agent_chat_properties.py` 中实现
  - [ ]* 11.5 编写属性测试：RAG 降级不阻塞对话
    - **Property: RAG failure does not block conversation**
    - **Validates: Requirements AG4.3**
    - Hypothesis 生成随机查询，模拟 RAG 返回空，验证 LLM 回复仍然生成
    - 在 `backend/tests/test_agent_chat_properties.py` 中实现

- [ ] 12. Final checkpoint — 确保所有测试通过
  - 确保所有单元测试通过
  - 确保属性测试通过（每个至少 100 次迭代）
  - 确保前端 lint 和类型检查通过
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key integration points
- 所有 Python 代码使用 Python 3.11+，async/await，类型注解完整
- 所有 TypeScript 代码使用严格模式，无 `any`
- LLM 适配器复用 `langchain` 社区包（`langchain-openai`、`langchain-deepseek` 等）
- MiniMax 如无现成 langchain 包，可直接使用 `httpx` 调用 MiniMax REST API
- RAG 检索工具复用 `qdrant-client` 的 `AsyncQdrantClient`
- 短期记忆复用已有的 `agent/memory/short_term.py:ShortTermMemory`
- 提示词复用已有的 `agent/prompts/customer_service.py:CUSTOMER_SERVICE_PROMPT`
