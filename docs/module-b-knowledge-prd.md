# 模块 B：RAG 知识库与记忆 — 产品需求文档

## 1. 文档目标

本文档定义模块 B（RAG 知识库）的功能范围、数据模型、API 接口设计、交互流程及验收标准，用于指导后端实现、前端联调与质量验收。

---

## 2. 模块概述

### 2.1 核心价值

解决"Agent 懂不懂行"的问题 — 为 AI 回复提供事实依据和品牌风格参考，让客服回复更专业、内容生成更有爆款质感。

### 2.2 用户故事

- **上传产品资料**：商家上传 PDF/Word/Markdown 等品牌文档，让 AI 能基于最新产品信息生成回复
- **管理爆款文案**：商家标记历史高互动笔记，让 AI 生成内容时能参考经过验证的爆款风格
- **智能检索**：商家提问时，系统能同时理解语义和匹配关键词，返回最相关的参考内容
- **多轮对话记忆**：客户在私信中多次沟通，系统记得之前说了什么，用户无需重复背景
- **行业情报追踪**：系统自动抓取小红书行业爆款笔记，商家可分析趋势获得选题灵感

---

## 3. 功能模块详细说明

### 3.1 B1 — 多格式知识上传

#### 功能描述

商家可将产品手册、品牌故事、FAQ 等资料上传至知识库，系统自动解析文档、分块处理（每块 ≤512 token，50 token 重叠）、建立向量索引。

#### 支持格式

| 格式 | 说明 |
|------|------|
| PDF | 最常见的产品文档格式 |
| DOCX | Word 文档 |
| Markdown | 轻量文档 |
| TXT | 纯文本 |
| URL | 网页内容（抓取后解析） |

#### 业务流程

```
上传文件 → 解析文档 → 分块（≤512 token，50 重叠）→ 向量化 → 存入 Qdrant
```

#### 状态说明

| 状态 | 说明 |
|------|------|
| `pending` | 待处理 |
| `processing` | 解析/索引中 |
| `indexed` | 已索引 |
| `failed` | 失败（可重试） |

#### 验收标准

1. 支持五种格式上传，5 分钟内完成向量索引
2. 每块不超过 512 token，相邻块保留 50 token 重叠
3. 支持删除和更新文档，更新后 2 分钟内完成重索引
4. 解析失败时返回明确错误，不影响其他文档

---

### 3.2 B2 — 爆款文案库管理

#### 功能描述

商家标记历史爆款笔记（含点赞、收藏、发布时间等互动数据），系统每 24 小时自动回抓最新互动数据，并根据互动率变化动态调整文案权重。

#### 互动率计算

```
互动率 = (点赞数 + 收藏数) / 发布天数
```

#### 权重调整规则

| 条件 | 调整幅度 |
|------|---------|
| 互动率 > 账号历史均值 1.5 倍 | 权重 ×1.2（提升 20%）|
| 互动率 < 账号历史均值 50% | 权重 ×0.9（降低 10%）|

#### 验收标准

1. 支持标记和上传历史爆款文案，包含互动数据标签
2. 每 24 小时自动回抓已发布笔记的阅读量、点赞数、收藏数、评论数
3. 回抓完成后计算互动率，与账号历史均值比较
4. 触发权重调整时，记录时间、原因、幅度，保留 30 天

---

### 3.3 B3 — 检索优化策略（混合检索）

#### 功能描述

检索时同时执行向量语义搜索和 BM25 关键词搜索，通过 RRF（倒数排名融合）重排后返回前 5 条最相关结果。

#### RRF 算法说明

```
RRF_score = Σ (1 / (k + rank))
k = 60（默认）
```

#### 降级处理

当所有结果相似度分数 < 0.6 时，返回空结果，通知调用方使用通用话术模板。

#### Few-shot 参考

内容生成时，自动从知识库检索至少 3 条高权重爆款文案作为风格参考。

#### 验收标准

1. 混合搜索：向量 + BM25 双路检索，RRF 重排返回 Top 5
2. 返回结果附带相似度分数和来源文档标识
3. 所有结果 < 0.6 时返回空，执行降级处理
4. 内容生成时融合至少 3 条爆款文案作为 Few-shot

---

### 3.4 B4 — 对话上下文维护

#### 功能描述

在私信多轮对话中保持上下文连贯，系统维护短期记忆（当前会话）和长期记忆（用户偏好）。

#### 上下文保留规则

| 条件 | 行为 |
|------|------|
| 用户最后一条消息在 30 分钟内 | 维持多轮上下文，保留最近 10 轮 |
| 用户最后一条消息 > 30 分钟 | 标记为"待跟进"，停止自动回复 |
| 连续 3 次无响应 | 停止自动回复，标记"待跟进" |

#### 长期记忆

- 持久化存储用户偏好标签
- 新会话开始时加载历史偏好作为上下文参考
- 保留周期不少于 90 天

#### 验收标准

1. 活跃会话（30 分钟内）保留最近 10 轮对话记录
2. 每个用户维护短期记忆（会话上下文）和长期记忆（偏好标签）
3. 长期记忆保留 90 天以上
4. 新会话开始时自动加载用户历史偏好
5. 连续 3 次无响应停止自动回复，标记待跟进

---

### 3.5 B5 — 行业爆款情报采集

#### 功能描述

商家配置行业关键词（如"护肤"、"咖啡"、"健身"），系统每 24 小时自动抓取该关键词下互动率排名前 50 的笔记。

#### 采集字段

| 字段 | 说明 |
|------|------|
| 标题 | 笔记标题 |
| 正文摘要 | 前 500 字 |
| 话题标签 | #话题 |
| 封面风格标签 | 真人出镜/产品平铺/图文混排 |
| 点赞数、收藏数、评论数 | 互动数据 |
| 发布时间 | 精确到天 |
| 发布账号粉丝量级 | 如"10万+" |

#### 存储位置

行业爆款存入独立 Qdrant 集合，与商家自有文案库隔离。

#### 验收标准

1. 支持配置多个行业关键词，每 24 小时自动采集
2. 采集字段包含标题、正文摘要、话题标签、封面风格、互动数据、发布时间、粉丝量级
3. 存入独立集合，与商家自有文案库隔离
4. 因限流导致不足 50 条时记录实际数量，继续执行不中断

---

### 3.6 B6 — 行业趋势分析与选题建议

#### 功能描述

基于行业爆款数据分析内容趋势，生成具体选题建议和爆款潜力评分。

#### 趋势分析输出

| 分析项 | 说明 |
|------|------|
| 高频话题标签 Top 10 | 最近 7 天最热门的话题 |
| 高互动标题结构模式 | 如"X 个方法"、"亲测有效"、"保姆级教程" |
| 最佳发布时间段 | 按小时统计互动率分布 |
| 封面风格偏好 | 真人出镜 / 产品平铺 / 图文混排占比 |

#### 选题建议输出

每条建议包含：
- 推荐标题
- 核心卖点角度
- 建议话题标签（3-5 个）
- 参考爆款笔记来源
- 爆款潜力评分（0-100 分）

#### 数据量要求

数据不足 10 条时，提示"数据量不足，建议等待下次采集后再查看"，不输出低置信度报告。

#### 验收标准

1. 基于最近 7 天爆款数据输出高频话题标签、高互动标题结构、最佳发布时间、封面风格偏好
2. 提交关键词后生成不少于 3 条选题建议
3. 每条建议附带爆款潜力评分（0-100）
4. 查看建议详情时展示 3-5 篇参考爆款笔记
5. 数据不足 10 条时提示数据量不足

---

## 4. 数据模型

### 4.1 ER 图

```
KnowledgeDocument (1) ─────< KnowledgeChunk (多)
                              │
                              └─── Qdrant (向量存储)

ViralCopy (1) ─────< WeightAdjustmentLog (多)
                         │
                         └─── Qdrant (向量存储)

IndustryNote ───── Qdrant (独立集合)
     │
     └─── TopicSuggestion (1) ───── ReferenceNote (关联)

ConversationContext (对话上下文)
     │
     └─── SearchHistory (检索历史)
```

### 4.2 表结构

#### `knowledge_documents` — 知识文档主表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 商家 ID |
| title | VARCHAR(256) | 文档标题 |
| file_type | VARCHAR(32) | pdf/docx/markdown/txt/url |
| file_path | TEXT | 文件路径或 URL |
| status | ENUM | pending/processing/indexed/failed |
| metadata | JSONB | 原始文档元信息 |
| chunk_count | INTEGER | 分块数量 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### `knowledge_chunks` — 文档分块表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| document_id | UUID | 关联文档 ID |
| content | TEXT | 分块内容 |
| token_count | INTEGER | token 数量 |
| chunk_index | INTEGER | 块序号 |
| vector_id | VARCHAR(128) | Qdrant 向量 ID |

#### `viral_copies` — 爆款文案库

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 商家 ID |
| account_id | UUID | 关联账号 ID |
| content | TEXT | 文案内容 |
| title | VARCHAR(256) | 笔记标题 |
| likes | INTEGER | 点赞数 |
| collects | INTEGER | 收藏数 |
| comments | INTEGER | 评论数 |
| published_at | TIMESTAMP | 发布时间 |
| weight | FLOAT | 检索权重（默认 1.0）|
| weight_adjusted_at | TIMESTAMP | 最近调整时间 |
| engagement_rate | FLOAT | 互动率 |
| created_at | TIMESTAMP | 创建时间 |

#### `weight_adjustment_logs` — 权重调整日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| viral_copy_id | UUID | 关联爆款文案 ID |
| old_weight | FLOAT | 调整前权重 |
| new_weight | FLOAT | 调整后权重 |
| reason | VARCHAR(128) | 调整原因 |
| created_at | TIMESTAMP | 创建时间 |

#### `industry_notes` — 行业爆款笔记

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 商家 ID |
| keyword | VARCHAR(64) | 行业关键词 |
| title | VARCHAR(256) | 笔记标题 |
| body | TEXT | 正文摘要 |
| tags | TEXT[] | 话题标签数组 |
| cover_style | VARCHAR(32) | 封面风格 |
| likes | INTEGER | 点赞数 |
| collects | INTEGER | 收藏数 |
| comments | INTEGER | 评论数 |
| published_at | TIMESTAMP | 发布时间 |
| author_fans | VARCHAR(32) | 账号粉丝量级 |
| engagement_rate | FLOAT | 互动率 |
| created_at | TIMESTAMP | 创建时间 |

#### `topic_suggestions` — 选题建议

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 商家 ID |
| keyword | VARCHAR(64) | 行业关键词 |
| suggested_title | VARCHAR(256) | 推荐标题 |
| core_selling_point | TEXT | 核心卖点角度 |
| tags | TEXT[] | 建议话题标签 |
| potential_score | INTEGER | 爆款潜力评分（0-100）|
| reference_notes | JSONB | 参考爆款笔记列表 |
| created_at | TIMESTAMP | 创建时间 |

#### `conversation_contexts` — 对话上下文

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 商家 ID |
| xhs_user_id | VARCHAR(64) | 小红书用户 ID |
| turns | JSONB | 对话轮次记录 [{role, content, timestamp}] |
| last_message_at | TIMESTAMP | 最后消息时间 |
| is_active | BOOLEAN | 是否活跃 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### `search_histories` — 检索历史

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| merchant_id | UUID | 商家 ID |
| query | TEXT | 搜索词 |
| hit_count | INTEGER | 命中数量 |
| high_quality_hit | BOOLEAN | 是否命中高质量内容 |
| created_at | TIMESTAMP | 创建时间 |

---

## 5. API 接口设计

### 5.1 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/knowledge/documents` | 上传文档 |
| GET | `/api/v1/knowledge/documents` | 文档列表（cursor 分页）|
| GET | `/api/v1/knowledge/documents/{id}` | 文档详情 |
| DELETE | `/api/v1/knowledge/documents/{id}` | 删除文档 |
| POST | `/api/v1/knowledge/documents/{id}/reindex` | 重新索引 |

### 5.2 检索

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/knowledge/search` | 混合检索 |
| GET | `/api/v1/knowledge/search/history` | 检索历史 |

### 5.3 爆款文案库

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/knowledge/viral-copies` | 添加爆款文案 |
| GET | `/api/v1/knowledge/viral-copies` | 爆款文案列表 |
| PUT | `/api/v1/knowledge/viral-copies/{id}` | 更新互动数据 |
| DELETE | `/api/v1/knowledge/viral-copies/{id}` | 删除 |

### 5.4 行业情报

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/knowledge/industry-notes` | 行业爆款笔记列表 |
| POST | `/api/v1/knowledge/industry-notes/crawl` | 触发采集 |
| GET | `/api/v1/knowledge/trends/{keyword}` | 趋势分析 |
| POST | `/api/v1/knowledge/topics/suggest` | 选题建议 |

### 5.5 配置与统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/knowledge/settings` | 获取检索设置 |
| PUT | `/api/v1/knowledge/settings` | 更新检索设置 |
| GET | `/api/v1/knowledge/stats` | 知识库统计 |

### 5.6 对话上下文（内部调用）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/knowledge/context/{xhs_user_id}` | 更新对话上下文 |
| GET | `/api/v1/knowledge/context/{xhs_user_id}` | 获取对话上下文 |

---

## 6. 响应格式

### 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

- `code: 0` = 成功，非零 = 业务错误
- 错误码范围：40101–40199（知识库模块）

### 分页响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "next_cursor": "xxx",
    "has_more": false
  }
}
```

---

## 7. 前端页面结构（已实现）

```
知识库页面 /knowledge
├── 知识库概览卡（4 个 StatCard）
│   ├── 文档总数
│   ├── 已索引条目
│   ├── 待处理文件
│   └── 检索命中率
├── 上传文档卡片
│   ├── 拖拽上传区域
│   ├── 混合检索开关状态
│   └── 向量权重显示
├── 索引进度卡片
│   ├── 进度条
│   ├── 高质量命中数
│   ├── 平均召回率
│   └── 检索规则说明
├── 文档列表表格
│   ├── 文件名、类型、大小、状态、更新时间
│   └── 重新索引按钮
└── 最近查询列表
    ├── 搜索词
    ├── 命中数量
    └── 质量评价
```

---

## 8. 验收检查清单

### B1 — 多格式知识上传
- [ ] 支持 PDF、DOCX、Markdown、TXT、URL 五种格式
- [ ] 上传后 5 分钟内完成索引
- [ ] 分块 ≤512 token，50 token 重叠
- [ ] 删除和更新后 2 分钟内完成重索引
- [ ] 解析失败返回明确错误

### B2 — 爆款文案库管理
- [ ] 支持标记和上传爆款文案含互动标签
- [ ] 每 24 小时自动回抓互动数据
- [ ] 互动率 >1.5 倍时权重提升 20%
- [ ] 互动率 <50% 时权重降低 10%
- [ ] 权重调整日志保留 30 天

### B3 — 检索优化策略
- [ ] 混合检索（向量 + BM25 + RRF）
- [ ] 返回 Top 5 结果含相似度分数
- [ ] 分数 <0.6 时返回空，降级处理
- [ ] 内容生成融合 3 条爆款文案

### B4 — 对话上下文维护
- [ ] 活跃会话保留最近 10 轮
- [ ] 长期记忆保留 90 天以上
- [ ] 新会话加载历史偏好
- [ ] 连续 3 次无响应标记待跟进

### B5 — 行业爆款情报采集
- [ ] 支持配置多个行业关键词
- [ ] 每 24 小时自动采集 Top 50
- [ ] 采集字段完整（标题、正文、标签、互动数据等）
- [ ] 存入独立集合，与商家文案库隔离

### B6 — 行业趋势分析与选题建议
- [ ] 输出高频话题标签 Top 10
- [ ] 输出高互动标题结构模式
- [ ] 输出最佳发布时间段分布
- [ ] 生成不少于 3 条选题建议
- [ ] 每条建议含潜力评分（0-100）
- [ ] 数据不足 10 条时提示不足
