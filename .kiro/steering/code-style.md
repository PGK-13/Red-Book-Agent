---
inclusion: always
---

# 代码风格规范

## Python（后端 / Agent / Worker）

- 使用 Python 3.11+
- 格式化工具：`black`，行宽 88
- Import 排序：`isort`，profile = black
- 类型注解：所有函数参数和返回值必须有类型注解
- Docstring：公共函数和类使用 Google 风格 docstring
- 异步优先：IO 操作一律使用 `async/await`，禁止在异步上下文中使用同步阻塞调用

```python
# Good
async def get_account(account_id: UUID, db: AsyncSession) -> Account | None:
    """获取账号信息。

    Args:
        account_id: 账号唯一标识
        db: 数据库会话

    Returns:
        账号对象，不存在时返回 None
    """
    ...

# Bad
def get_account(account_id, db):
    ...
```

## TypeScript（前端）

- 使用 TypeScript strict 模式，禁止 `any`
- 格式化工具：`prettier`
- 组件文件使用 PascalCase，工具函数文件使用 camelCase
- React 组件优先使用 Server Components，仅在需要交互时使用 `"use client"`

## 命名约定

| 场景 | 风格 | 示例 |
|------|------|------|
| Python 变量/函数 | snake_case | `account_id`, `get_account` |
| Python 类 | PascalCase | `AccountService` |
| Python 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| TypeScript 变量/函数 | camelCase | `accountId`, `getAccount` |
| TypeScript 组件 | PascalCase | `AccountCard` |
| TypeScript 类型/接口 | PascalCase | `AccountResponse` |
| 数据库表名 | snake_case 复数 | `accounts`, `content_drafts` |
| API 路径 | kebab-case | `/api/v1/viral-copies` |
