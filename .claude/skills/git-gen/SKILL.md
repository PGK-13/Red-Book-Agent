---
name: git-gen
description: Generate Conventional Commits compliant branch names, commit messages, and PR titles from code changes
---

# Git Gen

根据代码变更自动生成符合项目规范的 Git 分支名、提交信息和 PR 标题。

## Usage

```
/git-gen
```

无参数 — 自动分析当前工作区的变更（`git status` + `git diff`），生成分支名、提交信息、PR 标题。

## 项目规范

### 分支命名

```
feature/<module>-<description>   # 新功能
fix/<module>-<description>       # 修复
chore/<module>-<description>     # 杂项（依赖、配置、重构）
```

- `<module>` 使用短横线小写：`account`, `knowledge`, `content`, `interaction`, `risk`, `analytics`, `agent-chat`, `frontend`, `infra`
- `<description>` 用英文短横线连接，2-5 个词，如 `add-rag-retrieval`, `fix-cookie-expiry-check`

### 提交信息 (Conventional Commits)

```
<type>(<scope>): <subject>
```

- **type**: `feat` | `fix` | `chore` | `docs` | `test` | `refactor` | `style`
- **scope**: 模块名或文件名，如 `knowledge`, `agent-chat`, `frontend`, `account`, `risk`
- **subject**: 英文小写开头，动词原形开头，无句号结尾，≤ 72 字符

正确示例：
- `feat(knowledge): add RAG retrieval tool with Qdrant hybrid search`
- `fix(account): correct cookie expiry status transition`
- `chore(infra): update docker-compose to include Qdrant`

错误示例：
- `feat(knowledge): Added RAG retrieval tool.` (首字母大写，有句号)
- `fix: cookie bug` (缺少 scope)
- `update code` (缺少 type 和 scope)

### PR 标题

与提交信息同格式，描述整个 PR 的变更意图，≤ 70 字符:

```
<type>(<scope>): <简短描述>
```

## Workflow

### Step 1: 分析变更

```bash
git status        # 查看变更文件列表
git diff --stat   # 查看变更统计
git diff           # 查看具体变更内容
git log --oneline -10  # 查看最近提交风格
```

### Step 2: 识别变更类型和范围

根据变更内容判断:
- 新文件/新功能 → `feat`
- 修复已有 bug → `fix`
- 依赖更新、配置修改、代码清理 → `chore`
- 仅文档 → `docs`
- 仅测试 → `test`
- 重构（无功能变化）→ `refactor`

根据变更文件路径推断 scope:
- `backend/app/services/knowledge_service.py` → `knowledge`
- `frontend/components/Sidebar.tsx` → `frontend`
- `agent/tools/rag_retrieval.py` → `knowledge` 或 `agent`
- 多模块变更 → 选主要模块

### Step 3: 生成并输出

输出以下内容供用户选择/修改:

```
## 分支名
feature/knowledge-add-rag-retrieval-tool

## 提交信息
feat(knowledge): add RAG retrieval tool with Qdrant hybrid search

## PR 标题
feat(knowledge): add RAG retrieval tool with Qdrant hybrid search
```

### Step 4: 用户确认后执行

如果用户确认，执行:
- `git checkout -b <branch>` (如果还在 main 上)
- 提醒用户 PR 描述应补充: 变更动机、测试方式、截图（如有 UI 变更）

## Notes

- 如果当前分支已不是 `main`/`develop`，只生成提交信息和 PR 标题，不生成分支名
- 如果变更涉及多个不相关的功能，建议拆分为多个 PR
- PR 标题英文 ≤ 70 字符，中文部分可放在 PR body
