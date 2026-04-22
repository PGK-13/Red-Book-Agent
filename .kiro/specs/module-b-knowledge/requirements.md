# 模块 B：RAG 知识库与记忆 (Knowledge & Memory)

**核心价值**：解决"Agent 懂不懂行"的问题，提供事实依据和品牌风格参考。

---

## 需求 B1：多格式知识上传

**用户故事：** 作为商家，我希望能上传多种格式的品牌资料，以便系统能基于最新的产品信息生成准确回复。

### 验收标准

1. THE RAG 知识库 SHALL 支持商家上传 PDF、Docx、Markdown、纯文本和 URL 五种格式的产品手册，并在上传后 5 分钟内完成向量化索引。
2. WHEN 商家上传新文档，THE RAG 知识库 SHALL 对文档进行分块处理，每块不超过 512 个 token，相邻块之间保留 50 个 token 的重叠。
3. THE RAG 知识库 SHALL 支持商家删除或更新已索引文档，更新操作 SHALL 在 2 分钟内完成重新索引。
4. IF 文档解析失败（格式损坏或内容为空），THEN THE RAG 知识库 SHALL 向商家返回包含失败原因的错误提示，不影响其他已索引文档的正常使用。

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/knowledge/documents` | 上传文档 |
| GET | `/api/v1/knowledge/documents` | 文档列表（cursor 分页）|
| GET | `/api/v1/knowledge/documents/{id}` | 文档详情 |
| DELETE | `/api/v1/knowledge/documents/{id}` | 删除文档 |
| POST | `/api/v1/knowledge/documents/{id}/reindex` | 重新索引 |

### 数据模型

```
POST /api/v1/knowledge/documents
Request Body (JSON):
{
  "title": "产品手册v2",
  "file_type": "pdf" | "docx" | "markdown" | "txt" | "url",
  "file_path": "/uploads/xxx.pdf" | "https://example.com/doc",
  "metadata": { ... }
}

Response (201):
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "uuid",
    "title": "产品手册v2",
    "file_type": "pdf",
    "file_path": "/uploads/xxx.pdf",
    "file_size": 12.4,
    "status": "pending",
    "chunk_count": 0,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}

GET /api/v1/knowledge/documents?limit=20&cursor=<opaque_cursor>
Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "爆款文案库.pdf",
        "file_type": "pdf",
        "file_size": 12.4,
        "status": "indexed",
        "chunk_count": 42,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:05:00Z"
      }
    ],
    "next_cursor": "xxx",
    "has_more": false
  }
}
```

---

## 需求 B2：爆款文案库管理

**用户故事：** 作为商家，我希望能管理历史高互动文案库，以便系统在生成新内容时能参考经过验证的爆款风格。

### 验收标准

1. THE RAG 知识库 SHALL 支持商家标记和上传历史爆款文案，每条文案需包含互动数据标签（点赞数、收藏数、发布时间）用于检索排序。
2. THE 营销 Agent SHALL 每 24 小时自动回抓所有已发布笔记的阅读量、点赞数、收藏数和评论数，并将最新数据更新至数据库。
3. WHEN 数据回抓完成，THE RAG 知识库 SHALL 计算每篇笔记的互动率（点赞数 + 收藏数）并与该账号的历史互动率均值进行比较。
4. WHEN 笔记互动率高于账号历史均值的 1.5 倍，THE RAG 知识库 SHALL 将该笔记对应文案的检索权重自动提升 20%。
5. WHEN 笔记互动率低于账号历史均值的 50%，THE RAG 知识库 SHALL 将该笔记对应文案的检索权重自动降低 10%。
6. THE RAG 知识库 SHALL 记录每次权重调整的时间、触发原因和调整幅度，日志保留周期不少于 30 天。

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/knowledge/viral-copies` | 添加爆款文案 |
| GET | `/api/v1/knowledge/viral-copies` | 爆款文案列表 |
| PUT | `/api/v1/knowledge/viral-copies/{id}` | 更新互动数据 |
| DELETE | `/api/v1/knowledge/viral-copies/{id}` | 删除 |

### 数据模型

```
POST /api/v1/knowledge/viral-copies
Request Body:
{
  "account_id": "uuid",
  "content": "笔记正文内容...",
  "title": "笔记标题",
  "likes": 1523,
  "collects": 892,
  "comments": 156,
  "published_at": "2024-01-01T00:00:00Z"
}

Response (201):
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "uuid",
    "merchant_id": "uuid",
    "account_id": "uuid",
    "content": "笔记正文内容...",
    "title": "笔记标题",
    "likes": 1523,
    "collects": 892,
    "comments": 156,
    "published_at": "2024-01-01T00:00:00Z",
    "weight": 1.0,
    "weight_adjusted_at": null,
    "engagement_rate": 0.024,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

## 需求 B3：检索优化策略

**用户故事：** 作为商家，我希望系统的知识检索能兼顾语义相关性和关键词精确匹配，以便在不同场景下都能返回最准确的参考内容。

### 验收标准

1. WHEN 检索请求到达，THE RAG 知识库 SHALL 执行混合搜索策略：同时进行向量语义搜索和 BM25 关键词搜索，并对两路结果进行 RRF（倒数排名融合）重排后返回前 5 条结果。
2. THE RAG 知识库 SHALL 在返回检索结果时附带每条结果的相似度分数和来源文档标识。
3. IF 检索结果中所有条目的相似度分数均低于 0.6，THEN THE RAG 知识库 SHALL 返回空结果并通知调用方执行降级处理（如使用通用话术模板）。
4. THE 内容生成引擎 SHALL 从 RAG 知识库中检索至少 3 条相关爆款文案作为 Few-shot 风格参考，并将其融入生成结果。

### RRF 算法

```
RRF_score = Σ (1 / (k + rank))
k = 60（默认）
```

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/knowledge/search` | 混合检索 |
| GET | `/api/v1/knowledge/search/history` | 检索历史 |

### 数据模型

```
POST /api/v1/knowledge/search
Request Body:
{
  "query": "这款精华适合油皮吗",
  "top_k": 5,
  "vector_weight": 0.65
}

Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "query": "这款精华适合油皮吗",
    "chunks": [
      {
        "id": "uuid",
        "document_id": "uuid",
        "content": "该产品采用水基底配方...",
        "token_count": 256,
        "chunk_index": 3,
        "similarity_score": 0.847
      }
    ],
    "total": 5,
    "degraded": false
  }
}
```

---

## 需求 B4：对话上下文维护

**用户故事：** 作为商家，我希望系统能在私信多轮对话中保持上下文连贯，以便用户不需要重复说明背景信息。

### 验收标准

1. WHILE 私信对话处于活跃状态（用户最后一条消息在 30 分钟内），THE 私信转化器 SHALL 维持多轮对话上下文，保留最近 10 轮对话记录。
2. THE 营销 Agent SHALL 为每个用户维护短期记忆（当前会话上下文）和长期记忆（历史购买意向、偏好标签），长期记忆持久化存储，保留周期不少于 90 天。
3. WHEN 同一用户在不同时间发起新的私信会话，THE 私信转化器 SHALL 从长期记忆中加载该用户的历史偏好标签，作为本次回复的参考上下文。
4. IF 私信转化器连续 3 次回复后用户无响应，THEN THE 营销 Agent SHALL 停止自动回复并将该会话标记为"待跟进"，保留完整对话记录。

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/knowledge/context/{xhs_user_id}` | 更新对话上下文 |
| GET | `/api/v1/knowledge/context/{xhs_user_id}` | 获取对话上下文 |

### 数据模型

```
ConversationContext:
{
  "id": "uuid",
  "merchant_id": "uuid",
  "xhs_user_id": "xhs_user_123",
  "turns": [
    {"role": "user", "content": "这款产品多少钱", "timestamp": "2024-01-01T10:00:00Z"},
    {"role": "assistant", "content": "感谢咨询，这款产品售价299元...", "timestamp": "2024-01-01T10:00:05Z"}
  ],
  "last_message_at": "2024-01-01T10:00:05Z",
  "is_active": true
}

Update Context Request:
{
  "new_turn": {
    "role": "user" | "assistant",
    "content": "message content",
    "timestamp": "2024-01-01T10:00:00Z"
  }
}
```

---

## 需求 B5：行业爆款情报采集

**用户故事：** 作为商家，我希望系统能自动抓取指定行业在小红书上的当前爆款笔记，以便了解行业内容趋势并为自己的创作提供参考。

### 验收标准

1. THE 行业情报采集器 SHALL 支持商家配置一个或多个行业关键词（如"护肤"、"咖啡"、"健身"），系统每 24 小时自动抓取该关键词下互动率排名前 50 的笔记数据。
2. WHEN 行业情报采集器完成抓取，THE 行业情报采集器 SHALL 提取每篇笔记的以下字段：标题、正文摘要、话题标签、封面图风格标签、点赞数、收藏数、评论数、发布时间、发布账号粉丝量级。
3. THE 行业情报采集器 SHALL 将抓取到的行业爆款笔记向量化后存入 RAG 知识库的独立集合（与商家自有文案库隔离），供内容生成引擎检索参考。
4. IF 行业情报采集器在单次抓取中因平台限流导致数据不足 50 条，THEN THE 行业情报采集器 SHALL 记录实际抓取数量并继续执行后续流程，不中断任务。

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/knowledge/industry-notes` | 行业爆款笔记列表 |
| POST | `/api/v1/knowledge/industry-notes/crawl` | 触发采集 |

### 数据模型

```
POST /api/v1/knowledge/industry-notes/crawl
Request Body:
{
  "keywords": ["护肤", "咖啡", "健身"],
  "limit": 50
}

Response (202):
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "uuid",
    "keywords": ["护肤", "咖啡", "健身"],
    "status": "pending"
  }
}

GET /api/v1/knowledge/industry-notes?keyword=护肤&limit=20&cursor=xxx
Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "keyword": "护肤",
        "title": "油皮必入！这款精华我用空了3瓶",
        "body": "作为资深油皮，我用过无数精华...",
        "tags": ["油皮精华", "护肤心得", "空瓶记"],
        "cover_style": "real_person",
        "likes": 8932,
        "collects": 4521,
        "comments": 892,
        "published_at": "2024-01-01T00:00:00Z",
        "author_fans": "10万+",
        "engagement_rate": 0.015,
        "created_at": "2024-01-02T00:00:00Z"
      }
    ],
    "next_cursor": "xxx",
    "has_more": false
  }
}
```

---

## 需求 B6：行业趋势分析与选题建议

**用户故事：** 作为商家，我希望系统能基于行业爆款数据分析出当前的内容趋势，并给我的下一篇笔记提供具体的选题和发布建议，以便提升笔记的爆款概率。

### 验收标准

1. WHEN 商家请求行业趋势分析，THE 趋势分析引擎 SHALL 基于最近 7 天的行业爆款数据，输出以下分析结果：高频话题标签 Top 10、高互动标题结构模式（如"X 个方法"、"亲测有效"等）、最佳发布时间段（按小时统计互动率分布）、封面风格偏好（真人出镜 / 产品平铺 / 图文混排）。
2. WHEN 商家提交笔记选题关键词，THE 趋势分析引擎 SHALL 结合行业爆款数据和商家 RAG 知识库，生成不少于 3 条选题建议，每条建议包含：推荐标题、核心卖点角度、建议话题标签（3-5 个）、参考爆款笔记来源。
3. THE 趋势分析引擎 SHALL 在选题建议中标注每条建议的"爆款潜力评分"（0-100 分），评分依据为该选题方向在行业爆款中的出现频率和平均互动率。
4. WHEN 商家查看某条选题建议的详情，THE 趋势分析引擎 SHALL 展示支撑该建议的 3-5 篇参考爆款笔记的标题和互动数据。
5. IF 指定行业关键词下的爆款数据不足 10 条（数据积累不足），THEN THE 趋势分析引擎 SHALL 向商家提示"数据量不足，建议等待下次采集后再查看分析结果"，不输出低置信度的分析报告。

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/knowledge/trends/{keyword}` | 趋势分析 |
| POST | `/api/v1/knowledge/topics/suggest` | 选题建议 |

### 数据模型

```
GET /api/v1/knowledge/trends/{keyword}?days=7
Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "keyword": "护肤",
    "top_tags": [
      {"tag": "油皮护肤", "count": 156},
      {"tag": "精华推荐", "count": 134},
      {"tag": "护肤分享", "count": 98}
    ],
    "title_patterns": [
      {"pattern": "X个方法", "examples": ["3个方法让你告别油皮", "5个方法淡化痘印"]},
      {"pattern": "亲测有效", "examples": ["亲测有效的控油方法", "亲测3个月的护肤记录"]}
    ],
    "best_publish_hours": [
      {"hour": 20, "engagement_rate": 0.028},
      {"hour": 21, "engagement_rate": 0.025},
      {"hour": 12, "engagement_rate": 0.018}
    ],
    "cover_style_preference": [
      {"style": "real_person", "ratio": 0.65},
      {"style": "product_flat", "ratio": 0.25},
      {"style": "mixed", "ratio": 0.10}
    ],
    "note_count": 523,
    "analyzed_at": "2024-01-01T00:00:00Z"
  }
}

POST /api/v1/knowledge/topics/suggest
Request Body:
{
  "keyword": "精华",
  "count": 3
}

Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "keyword": "精华",
    "suggestions": [
      {
        "id": "uuid",
        "suggested_title": "油皮亲妈！这款精华我用空了3瓶",
        "core_selling_point": "强调控油效果和真实使用感受，适合油皮用户",
        "tags": ["油皮精华", "控油护肤", "空瓶记"],
        "potential_score": 85,
        "reference_notes": [
          {"title": "油皮必入！这款精华我用空了3瓶", "likes": 8932, "collects": 4521},
          {"title": "夏天用这支精华，皮肤稳定多了", "likes": 5621, "collects": 3210}
        ]
      }
    ],
    "insufficient_data": false
  }
}
```

---

## 统计与配置 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/knowledge/stats` | 知识库统计 |
| GET | `/api/v1/knowledge/settings` | 获取检索设置 |
| PUT | `/api/v1/knowledge/settings` | 更新检索设置 |

### 数据模型

```
GET /api/v1/knowledge/stats
Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "total_docs": 28,
    "indexed_chunks": 2640,
    "pending_files": 3,
    "hit_rate": 0.86,
    "viral_copy_count": 156,
    "industry_note_count": 2340
  }
}

GET /api/v1/knowledge/settings
Response (200):
{
  "code": 0,
  "message": "success",
  "data": {
    "vector_weight": 0.65,
    "hybrid_enabled": true,
    "updated_at": "2024-01-01T00:00:00Z"
  }
}

PUT /api/v1/knowledge/settings
Request Body:
{
  "vector_weight": 0.7,
  "hybrid_enabled": true
}
```

---

## 正确性属性

| 属性 | 描述 | 验证需求 |
|------|------|----------|
| B-Attr-1 | 文档分块：所有分块 token 数 ≤ 512，相邻分块保留 50 token 重叠 | B1.2 |
| B-Attr-2 | 混合检索：返回结果数量 ≤ 5，所有分数 < 0.6 时返回空 | B3.1, B3.3 |
| B-Attr-3 | 权重调整：互动率 > 均值 1.5 倍 → 权重 ×1.2；< 均值 50% → 权重 ×0.9 | B2.4, B2.5 |
| B-Attr-4 | 权重调整日志：每次调整记录 old_weight、new_weight、reason、created_at，保留 ≥ 30 天 | B2.6 |
| B-Attr-5 | 对话上下文：活跃会话保留最近 10 轮，超时 30 分钟标记为待跟进 | B4.1 |
| B-Attr-6 | 长期记忆：保留周期 ≥ 90 天 | B4.2 |
| B-Attr-7 | 选题建议：数据不足 10 条时不输出低置信度报告 | B6.5 |

---

## 前端 API 对接规范

模块二前端页面（`frontend/app/(dashboard)/knowledge/page.tsx`）通过以下 API 获取数据。

### 页面加载时调用

```
GET /api/v1/knowledge/stats
  → 填充 4 个 StatCard

GET /api/v1/knowledge/documents?limit=100
  → 填充文档列表表格

GET /api/v1/knowledge/settings
  → 填充上传卡片（混合检索开关状态、向量权重）和检索设置卡片

GET /api/v1/knowledge/search/history?limit=10
  → 填充最近查询列表
```

### 前端组件数据映射

#### StatCard（4个概览统计卡）

| 前端显示 | 后端字段 | 说明 |
|----------|----------|------|
| 文档总数 | `total_docs` | knowledge_documents 表总数 |
| 已索引条目 | `indexed_chunks` | 已索引的分块总数 |
| 待处理文件 | `pending_files` | status = 'pending' 或 'processing' 的文档数 |
| 检索命中率 | `hit_rate` | 最近 7 天有结果的检索占比（0.86 表示 86%）|

```json
GET /api/v1/knowledge/stats
Response:
{
  "code": 0,
  "data": {
    "total_docs": 28,
    "indexed_chunks": 2640,
    "pending_files": 3,
    "hit_rate": 0.86,
    "viral_copy_count": 156,
    "industry_note_count": 2340
  }
}
```

#### 上传文档卡片

| 前端显示 | 后端字段 | 说明 |
|----------|----------|------|
| 混合检索状态 | `hybrid_enabled` | true = "已启用" |
| 向量权重 | `vector_weight` | 如 0.65 |

```json
GET /api/v1/knowledge/settings
Response:
{
  "code": 0,
  "data": {
    "vector_weight": 0.65,
    "hybrid_enabled": true,
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

#### 索引进度卡片

前端此卡片展示的是**最近一次检索的统计**，不是实时任务进度（实时进度通过 WebSocket/SSE 推送）。

| 前端显示 | 后端字段 | 说明 |
|----------|----------|------|
| 高质量命中 | `high_quality_hits` | 最近一次检索中相似度 > 0.8 的结果数 |
| 平均召回 | `avg_recall` | 最近 7 天检索的平均 recall 分数 |
| 更新时间 | `updated_at` | 最近一次检索的时间 |

> 注：索引进度卡片当前为静态展示，实现时可扩展为实时任务进度 API。

#### 文档列表表格

| 前端显示列 | 后端字段 | 格式化/映射规则 |
|------------|----------|----------------|
| 文件名 | `title` | 直接显示 |
| 类型 | `file_type` | `pdf` → "PDF", `docx` → "Word", `markdown` → "Markdown", `txt` → "TXT", `url` → "URL" |
| 大小 | `file_size` | 单位 MB，保留 1 位小数，如 `12.4 MB` |
| 状态 | `status` | `pending` → <Badge tone="neutral">待处理</Badge>, `processing` → <Badge tone="warning">索引中</Badge>, `indexed` → <Badge tone="success">已索引</Badge>, `failed` → <Badge tone="critical">失败</Badge> |
| 更新时间 | `updated_at` | 相对时间：< 60分钟显示"X分钟前"，< 24小时显示"X小时前"，否则显示日期 |

```json
GET /api/v1/knowledge/documents?limit=20&cursor=<cursor>
Response:
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "爆款文案库.pdf",
        "file_type": "pdf",
        "file_size": 12.4,
        "status": "indexed",
        "chunk_count": 42,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:05:00Z"
      }
    ],
    "next_cursor": "xxx",
    "has_more": false
  }
}
```

**file_type 显示映射表：**

| 存储值 | 前端显示 |
|--------|----------|
| `pdf` | "PDF" |
| `docx` | "Word" |
| `markdown` | "Markdown" |
| `txt` | "TXT" |
| `url` | "URL" |

#### 最近查询列表（TimelineItem）

```json
GET /api/v1/knowledge/search/history?limit=10
Response:
{
  "code": 0,
  "data": {
    "items": [
      {
        "query": "护肤种草文案",
        "hit_count": 8,
        "high_quality_hit": true,
        "created_at": "2024-01-01T10:00:00Z"
      }
    ]
  }
}
```

| 前端 TimelineItem 字段 | 来源 |
|------------------------|------|
| `title` | `"搜索词：" + query` |
| `description` | 动态生成，如"命中 {hit_count} 条高质量片段" |
| `time` | 相对时间 |
| `tone` | `high_quality_hit ? "success" : hit_count > 5 ? "accent" : "warning"` |

### 前端交互触发的 API

| 前端操作 | 触发 API | 说明 |
|----------|----------|------|
| 上传文件 | `POST /api/v1/knowledge/documents` | multipart/form-data |
| 删除文档 | `DELETE /api/v1/knowledge/documents/{id}` | |
| 重新索引 | `POST /api/v1/knowledge/documents/{id}/reindex` | |
| 保存检索设置 | `PUT /api/v1/knowledge/settings` | |
| 执行搜索 | `POST /api/v1/knowledge/search` | 搜索结果不直接展示在页面，通过 Agent 调用 |

### 前端状态 Badge 映射

```typescript
// 文档状态 → Badge tone
const statusMap = {
  pending: "neutral",    // 待处理
  processing: "warning", // 索引中
  indexed: "success",    // 已索引
  failed: "critical"     // 失败
};

// 检索历史 → TimelineItem tone
const toneMap = {
  high_quality_hit: true  -> "success",
  hit_count > 5           -> "accent",
  hit_count <= 5          -> "warning"
};
```

### 文件大小格式化规则

后端存储 `file_size` 为 MB 浮点数，前端格式化显示：
- `< 1 MB`：显示为 "0.x MB"
- `>= 1 MB`：保留 1 位小数，如 "12.4 MB"
- `>= 1000 MB`：显示为 "x.x GB"

---

## 错误码

知识库模块错误码范围：**40101–40199**

| 错误码 | 说明 |
|--------|------|
| 40101 | 文档上传失败 |
| 40102 | 文档解析失败 |
| 40103 | 文档索引失败 |
| 40104 | 文档不存在 |
| 40105 | 文档删除失败 |
| 40106 | 检索服务不可用 |
| 40107 | 行业采集失败 |
| 40108 | 趋势分析数据不足 |
| 40109 | 选题建议生成失败 |

---

## Celery 定时任务

| 任务 | 周期 | 说明 |
|------|------|------|
| `crawl_industry_notes_task` | 每 24 小时 | 采集行业爆款笔记 |
| `fetch_viral_copy_engagement_task` | 每 24 小时 | 回抓爆款文案互动数据 |
| `adjust_viral_copy_weights_task` | 每日回抓后 | 调整爆款文案权重 |
| `analyze_trends_task` | 每周 | 更新行业趋势分析 |
| `cleanup_old_contexts_task` | 每日 | 清理超过 90 天的长期记忆 |

---

## 依赖关系

```
B1 文档上传
  └── 调用 Qdrant 向量存储
  └── 调用文档解析服务（PDF/DOCX 解析）

B2 爆款文案管理
  ├── 依赖 B1（文案作为检索内容）
  └── 依赖 Celery 定时任务（回抓 + 权重调整）

B3 混合检索
  ├── 调用 Qdrant 向量检索
  ├── 调用 Qdrant BM25 检索
  └── 被 D 模块（互动服务）调用

B4 对话上下文
  ├── 存储于 PostgreSQL
  └── 被 D 模块（互动服务）调用

B5 行业情报采集
  └── 调用 Playwright 抓取小红书

B6 趋势分析
  ├── 依赖 B5（行业爆款数据）
  └── 依赖 LLM 生成选题建议
```

---

## PostgreSQL 表结构

### knowledge_documents（知识文档主表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 文档唯一标识 |
| merchant_id | UUID FK | 所属商家 |
| title | VARCHAR(256) | 文档标题 |
| file_type | ENUM | pdf/docx/markdown/txt/url |
| file_path | TEXT | 文件路径或 URL |
| file_size | FLOAT | 文件大小（MB），前端显示时保留 1 位小数 |
| status | ENUM | pending/processing/indexed/failed |
| metadata | JSONB | 原始文档元信息 |
| chunk_count | INT | 分块数量 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

### knowledge_chunks（文档分块表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 分块唯一标识 |
| document_id | UUID FK | 所属文档 |
| content | TEXT | 分块文本内容 |
| token_count | INT | Token 数量（≤ 512） |
| chunk_index | INT | 分块序号 |
| vector_id | VARCHAR(128) | Qdrant 向量 ID |

### viral_copies（爆款文案表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 文案唯一标识 |
| merchant_id | UUID FK | 所属商家 |
| account_id | UUID FK | 关联账号 |
| content | TEXT | 笔记正文 |
| title | VARCHAR(256) | 笔记标题 |
| likes | INT | 点赞数 |
| collects | INT | 收藏数 |
| comments | INT | 评论数 |
| published_at | TIMESTAMPTZ | 发布时间 |
| weight | FLOAT | 检索权重（默认 1.0）|
| weight_adjusted_at | TIMESTAMPTZ | 最近调整时间 |
| engagement_rate | FLOAT | 互动率 |
| created_at | TIMESTAMPTZ | 创建时间 |

### weight_adjustment_logs（权重调整日志表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 日志唯一标识 |
| viral_copy_id | UUID FK | 关联爆款文案 |
| old_weight | FLOAT | 调整前权重 |
| new_weight | FLOAT | 调整后权重 |
| reason | VARCHAR(128) | 调整原因 |
| created_at | TIMESTAMPTZ | 创建时间（保留 ≥ 30 天）|

### industry_notes（行业爆款笔记表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 记录唯一标识 |
| merchant_id | UUID FK | 所属商家 |
| keyword | VARCHAR(64) | 行业关键词 |
| title | VARCHAR(256) | 笔记标题 |
| body | TEXT | 正文摘要 |
| tags | TEXT[] | 话题标签数组 |
| cover_style | VARCHAR(32) | 封面风格 |
| likes | INT | 点赞数 |
| collects | INT | 收藏数 |
| comments | INT | 评论数 |
| published_at | TIMESTAMPTZ | 发布时间 |
| author_fans | VARCHAR(32) | 账号粉丝量级 |
| engagement_rate | FLOAT | 互动率 |
| created_at | TIMESTAMPTZ | 创建时间 |

### topic_suggestions（选题建议表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 建议唯一标识 |
| merchant_id | UUID FK | 所属商家 |
| keyword | VARCHAR(64) | 行业关键词 |
| suggested_title | VARCHAR(256) | 推荐标题 |
| core_selling_point | TEXT | 核心卖点角度 |
| tags | TEXT[] | 建议话题标签（3-5 个）|
| potential_score | INT | 爆款潜力评分（0-100）|
| reference_notes | JSONB | 参考爆款笔记列表 |
| created_at | TIMESTAMPTZ | 创建时间 |

### conversation_contexts（对话上下文表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 上下文唯一标识 |
| merchant_id | UUID FK | 所属商家 |
| xhs_user_id | VARCHAR(64) | 小红书用户 ID |
| turns | JSONB | 对话轮次记录 |
| last_message_at | TIMESTAMPTZ | 最后消息时间 |
| is_active | BOOLEAN | 是否活跃 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

### search_histories（检索历史表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 历史唯一标识 |
| merchant_id | UUID FK | 所属商家 |
| query | TEXT | 搜索词 |
| hit_count | INT | 命中数量 |
| high_quality_hit | BOOLEAN | 是否命中高质量内容 |
| created_at | TIMESTAMPTZ | 创建时间 |

### retrieval_settings（检索设置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 设置唯一标识 |
| merchant_id | UUID UNIQUE | 所属商家 |
| vector_weight | FLOAT | 向量权重（默认 0.65）|
| hybrid_enabled | BOOLEAN | 混合检索开关（默认 true）|
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |
