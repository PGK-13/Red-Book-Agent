---
inclusion: fileMatch
fileMatchPattern: "**/api/**,**/schemas/**,**/routers/**,**/routes/**"
---

# API 设计规范

## 响应格式

所有 API 统一返回以下结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

错误时：

```json
{
  "code": 40001,
  "message": "账号不存在",
  "data": null
}
```

- `code` 为 `0` 表示成功，非 `0` 表示业务错误
- HTTP 状态码仅用于表达传输层语义（200 / 400 / 401 / 403 / 404 / 500）
- 禁止在成功响应中使用 4xx/5xx 状态码

## 错误码约定

| 范围 | 含义 |
|------|------|
| 40001 ~ 40099 | 账号模块错误 |
| 40101 ~ 40199 | 知识库模块错误 |
| 40201 ~ 40299 | 内容生成模块错误 |
| 40301 ~ 40399 | 互动模块错误 |
| 40401 ~ 40499 | 风控模块错误 |
| 50001 ~ 50099 | 服务器内部错误 |

## 分页

列表接口统一使用 cursor 分页：

```
GET /api/v1/accounts?limit=20&cursor=<opaque_cursor>
```

响应：

```json
{
  "code": 0,
  "data": {
    "items": [],
    "next_cursor": "xxx",
    "has_more": true
  }
}
```

- 禁止使用 offset 分页（数据量大时性能差）
- `limit` 最大值为 100，默认 20

## 异步任务

耗时操作（内容生成、文档索引等）返回 `task_id`，客户端轮询状态：

```
POST /api/v1/content/generate  →  { "task_id": "xxx" }
GET  /api/v1/content/tasks/{task_id}  →  { "status": "pending|running|success|failed", "result": {} }
```

## 版本控制

- 当前版本：`/api/v1/`
- 破坏性变更必须升级版本号，旧版本保留至少 3 个月
