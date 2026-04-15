# CLAUDE.md (User Global)

This file is automatically loaded for every conversation, regardless of the project.

## My Preferences

- Respond in the same language as the user (Chinese or English)
- Keep responses concise and direct
- When the user is in plan mode, do not make edits — only read files and ask clarifying questions
- Before suggesting a change, check if a similar pattern already exists in the codebase to avoid duplication

##跨项目通用规范

### 部署安全红线
禁止执行任何将变更部署、推送或应用到远程环境的命令，包括：
- `docker push` / `docker-compose up` 针对远程环境
- 携带生产连接串的 `psql` / `pg_dump`
- 直接 SSH 到生产服务器
- `kubectl apply` / `helm upgrade` 针对生产集群

所有部署必须通过 CI/CD 流水线完成。

### 安全规范（全局）
- 所有密钥、API Key 必须通过环境变量注入，禁止硬编码
- 禁止在日志、响应体、错误信息中输出 token、密钥、cookie 原文
- `.env` 文件禁止提交至代码仓库

### Git 规范（全局）
- Commits 遵循 Conventional Commits：`feat(module): description`
- 分支命名：`feature/*` / `fix/*` / `chore/*`
- PR 必须关联 Issue，合并使用 Squash Merge

## 代码自验闭环

完成代码实现后，必须自行验证以下内容，验证通过后再继续：

### 每次实现后必做
1. **语法检查**：确认文件无语法错误，能被 Python/TypeScript 编译器识别
2. **类型检查**：运行 `mypy`（Python）或 `tsc --noEmit`（TypeScript）无错误
3. **格式化**：代码符合项目规范（black/isort 行宽 88，prettier）
4. **导入检查**：`python -c "import app"` 或 `tsc` 无 ImportError

### 有测试的情况下
5. **运行相关测试**：`pytest tests/path/to/test_file.py`
6. **若有测试失败**：先修复测试失败，再继续

### 无测试的情况下（可跳过5-6，但必须做7）
7. **写一个快速验证脚本**，验证核心逻辑的正确性（如边界条件、关键返回值）

### 验证后才算完成
- 验证结果必须汇报给用户（哪些通过、哪些失败、失败原因）
- 不通过的情况下，说明问题所在，不要绕过
