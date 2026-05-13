# Agent 对话系统 (Agent Chat)

**核心价值**：解决"如何测试和调试 RAG 检索效果"的问题，为商家和开发者提供一个统一的对话界面，支持多模型切换和 RAG 检索能力验证。

---

## 需求 AG1：对话导航入口

**用户故事：** 作为商家/开发者，我希望在侧边栏有一个"Agent 对话"入口，点击后进入对话页面，以便快速开始与 Agent 对话测试 RAG 效果。

### 验收标准

1. THE 主布局侧边栏 SHALL 在主导航区域新增"Agent 对话"导航项，使用聊天气泡图标，与其他导航项视觉风格一致。
2. WHEN 用户点击"Agent 对话"导航项，THE 系统 SHALL 路由到 `/agent-chat` 页面，该导航项 SHALL 高亮显示（粉色左侧指示条 + 粉色文字）。
3. THE "Agent 对话"导航项 SHALL 位于侧边栏主导航区域（与"数据看板""知识库"等并列），而非工具区。

---

## 需求 AG2：对话界面

**用户故事：** 作为商家/开发者，我希望看到一个清晰的对话界面，能发送消息并查看 Agent 回复和 RAG 参考来源，以便直观评估检索和回复质量。

### 验收标准

1. THE 对话页面 SHALL 包含三个区域：顶部标题栏（显示"Agent 对话"和当前对话 ID 摘要）、中间消息列表区、底部输入区。
2. THE 消息列表区 SHALL 以聊天气泡形式展示对话记录：用户消息右对齐、粉色背景白色文字；Agent 回复左对齐、浅灰背景深色文字。
3. WHEN Agent 回复包含 RAG 检索来源，THE 回复气泡下方 SHALL 展示"RAG 参考来源"折叠面板，每条来源显示内容摘要和相关度分数。
4. THE 输入区 SHALL 包含一个文本输入框和一个发送按钮，支持 Enter 发送、Shift+Enter 换行。
5. WHEN 消息正在发送并等待回复，THE 消息列表底部 SHALL 展示加载动画（三个跳动圆点），发送按钮 SHALL 变为不可点击状态。
6. IF 请求失败（网络错误或服务端错误），THEN THE 系统 SHALL 在消息列表中展示错误提示气泡（红色边框），不丢失已输入的文字。
7. THE 对话页面 SHALL 在新消息到达时自动滚动到最底部。
8. THE 对话页面 SHALL 在无消息时展示引导提示："开始与 Agent 对话，测试 RAG 检索效果"，居中显示聊天气泡图标。

---

## 需求 AG3：LLM 模型接入与切换

**用户故事：** 作为开发者，我希望能切换不同的 LLM 后端（如 GPT-4o、DeepSeek、MiniMax），以便对比不同模型在 RAG 场景下的回复质量。

### 验收标准

1. THE Agent 对话系统 SHALL 支持至少三种 LLM 后端：OpenAI（GPT-4o）、DeepSeek（deepseek-chat）、MiniMax（abab6.5s-chat）。
2. THE 对话页面顶部 SHALL 提供一个模型选择器（下拉菜单），列出所有可用模型，默认使用 MiniMax（abab6.5s-chat）。
3. WHEN 用户切换模型，THE 后续对话 SHALL 使用新选中的模型生成回复，已产生的历史消息不受影响。
4. THE LLM 调用 SHALL 通过 `BaseLLM` 抽象接口执行，新增模型只需实现 `chat()` 方法，无需修改对话路由逻辑。
5. IF 所选模型的 API 不可用（未配置 API Key 或服务不可达），THEN THE 系统 SHALL 返回明确错误信息，包含模型名称和错误原因。

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/agent/models` | 获取可用模型列表 |
| POST | `/api/v1/agent/chat` | 发送消息并获取回复 |

### 数据模型

```
GET /api/v1/agent/models
Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "models": [
      {"id": "deepseek-chat", "name": "DeepSeek", "available": true},
      {"id": "gpt-4o", "name": "GPT-4o", "available": true},
      {"id": "minimax-abab6.5s", "name": "MiniMax", "available": false}
    ]
  }
}

POST /api/v1/agent/chat
Request Body (JSON):
{
  "message": "这款产品适合油皮吗？",
  "conversation_id": "uuid-or-new",
  "model": "deepseek-chat"
}

Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "reply": "根据您的产品手册，这款精华...",
    "rag_sources": [
      {
        "content": "该产品采用水基底配方，适合油性皮肤...",
        "score": 0.847,
        "source_doc_id": "uuid"
      }
    ],
    "conversation_id": "uuid",
    "model": "deepseek-chat",
    "tokens_used": 350
  }
}
```

---

## 需求 AG4：RAG 检索集成

**用户故事：** 作为开发者，我希望 Agent 对话能自动调用 RAG 知识库检索，在回复中引用相关知识片段，以便验证检索质量（命中率、相关度）。

### 验收标准

1. WHEN 用户发送消息，THE Agent 对话系统 SHALL 自动以用户消息作为查询文本调用知识库检索（`POST /api/v1/knowledge/search`），将检索结果作为上下文注入 LLM 提示词。
2. THE Agent 对话系统 SHALL 在返回 LLM 回复的同时返回检索到的 RAG 来源列表，每条包含内容片段、相似度分数和来源文档 ID。
3. IF 检索结果中所有条目的相似度分数均低于 0.6，THEN Agent 回复中 SHALL 标明"未找到相关知识库内容"，LLM 使用通用知识回复。
4. THE Agent 对话系统 SHALL 在每次对话请求中附带 `rag_sources` 字段，即使为空也返回空数组，便于前端统一渲染。

---

## 需求 AG5：对话上下文管理

**用户故事：** 作为开发者，我希望对话能保持多轮上下文连贯，同时支持新建对话清空上下文，以便测试不同场景下的 RAG 检索效果。

### 验收标准

1. THE Agent 对话系统 SHALL 为每个 `conversation_id` 维护独立的对话上下文，保留最近 10 轮对话记录（基于 `ShortTermMemory`，Redis 存储，24 小时 TTL）。
2. WHEN 用户发送消息，THE Agent 对话系统 SHALL 从上下文存储中加载该会话的历史消息，与当前消息一同发送给 LLM。
3. WHEN 用户点击"新对话"按钮，THE 系统 SHALL 生成新的 `conversation_id`，清空当前页面消息列表，旧对话的上下文在 Redis 中保留至 TTL 过期。
4. THE 对话页面 SHALL 在页面刷新后保持相同的 `conversation_id`（通过 localStorage 持久化），自动恢复之前的对话上下文。
5. THE Agent 对话系统 SHALL 在每次请求时检查 `conversation_id` 是否有效，无效时自动生成新 ID 并返回。

---

## 正确性属性

| 属性 | 描述 | 验证需求 |
|------|------|----------|
| 模型切换隔离 | 切换模型不影响已有消息，仅后续请求使用新模型 | AG3 |
| RAG 降级处理 | 检索结果全低于 0.6 时仍返回回复，rag_sources 为空数组 | AG4 |
| 上下文窗口截断 | 超过 10 轮对话时自动截断最旧记录，Redis TTL 24h | AG5 |
| 会话持久化 | 页面刷新后 conversation_id 不变，上下文可恢复 | AG5 |
| 错误不丢输入 | 请求失败时已输入文字保留在输入框中 | AG2 |
| 多模型抽象 | 新增 LLM 后端只需实现 BaseLLM 接口 | AG3 |

---

## 错误码

| 错误码 | 说明 |
|--------|------|
| 40101 | 知识库检索失败 |
| 40102 | LLM 调用失败 |
| 40103 | 模型不可用 |
| 40104 | 对话上下文操作失败 |

---

## 前端 API 映射

| 前端功能 | API 端点 | 方法 |
|----------|----------|------|
| 发送消息 | `/api/v1/agent/chat` | POST |
| 获取模型列表 | `/api/v1/agent/models` | GET |
| 知识检索（内部调用） | `/api/v1/knowledge/search` | POST |

---

## 依赖关系

```
[AG1 导航入口] ──依赖──▶ [F2 主布局框架] (frontend-shell)
[AG2 对话界面] ──依赖──▶ [F3 视觉设计规范] (frontend-shell)
[AG3 LLM 接入] ──依赖──▶ [BaseLLM 抽象接口] (agent/llm/base.py)
[AG4 RAG 集成] ──依赖──▶ [B3 检索优化策略] (module-b-knowledge)
[AG5 上下文管理] ──依赖──▶ [B4 对话上下文维护] (module-b-knowledge)
```
