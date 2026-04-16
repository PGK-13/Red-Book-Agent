---
paths:
  - "**"
---

# Code Review Workflow

When the user asks to review a PR (by providing a PR link or branch name), follow this process:

## Step 1: Identify the Module and Requirements

1. Get PR details via `gh pr view <url>`
2. Read the branch name and commit messages to identify which module is being implemented
3. Map to the corresponding requirements file: `.kiro/specs/module-{letter}-{name}/requirements.md`
4. If the module is unclear from branch/commit, ask the user

## Step 2: Fetch the Code

```bash
gh pr checkout <pr-url>   # or git fetch + git checkout <branch>
gh pr diff <pr-url>        # get the full diff
```

## Step 3: Requirements Coverage Analysis

For each acceptance criterion in the requirements file:
- [ ] Read the corresponding code that should implement it
- [ ] Verify the implementation exists and is correct
- [ ] Check for missing edge cases, error handling, data isolation (merchant_id), sensitive field encryption

## Step 4: Code Quality Check

- Layering violations (business logic in routes? raw SQL in services?)
- Type annotations present and correct
- Security: encrypted fields use `_enc` suffix, no hardcoded secrets
- API conventions: response format, error codes, cursor pagination

## Step 5: Post Review Comments (Must Use PR Review Suggestions)

**CRITICAL: Every bug must be posted as a SEPARATE PR review comment on the specific file change, using GitHub's `suggestion` syntax.** Comments on the PR body (Issues) are NOT directly applicable by teammates. Each suggestion must be in a separate review comment so teammates can click "Commit suggestion" to apply it directly.

### How to Post Suggestions

Use the GitHub REST API to create multi-comment PR reviews with suggestion blocks:

```python
import subprocess

reviews = [
    {
        "bug_number": 1,
        "title": "[Bug 1] 简短问题描述",
        "body": "问题详细说明，包含为什么需要改、会产生什么后果。",
        "file": "backend/app/models/example.py",
        "line": 42,
        "suggestion": """```suggestion
正确的代码内容
```""",
    },
    # ... more bugs
]

for bug in reviews:
    cmd = [
        "gh", "api", "repos/OWNER/REPO/pulls/16/reviews", "--method", "POST",
        "--input", "-",
    ]
    payload = {
        "event": "COMMENT",
        "body": bug["body"],
        "comments": [{
            "path": bug["file"],
            "line": bug["line"],
            "side": "RIGHT",
            "body": bug["suggestion"],
        }],
    }
    # post via subprocess or requests
```

Or use `gh pr review --comment` with heredoc body, one review per bug.

### Comment Format Per Bug

Each bug gets its own review comment containing:

1. **Bug 编号和标题**: `[Bug N] 简短标题`
2. **问题描述**: 为什么是 bug、会产生什么后果
3. **文件路径和行号**: 精确到行
4. **suggestion 代码块**: 可直接 apply 的代码，用 ` ```suggestion` 语法

### Example

```
**[Bug 1] operation_log_status_enum 缺少 blocked 值**

analytics.py 定义的 enum 只有 ("success", "failed", "skipped")，但 risk_service.py 多处传入 "blocked"，PostgreSQL 写入时会报 enum value 错误。

**文件**: backend/app/models/analytics.py:15

suggested change:
```suggestion
operation_log_status_enum = Enum(
    "success",
    "failed",
    "skipped",
    "blocked",
    "rewrite_required",
    name="operation_log_status_enum",
)
```
```

### Verdict

Use one of:
- ✅ **Pass** — all requirements met, no blocking issues
- ⚠️ **Needs Changes** — blocking issues exist, must fix before merge
- ❌ **Block** — critical security/correctness issues

## Review Focus Areas by Module

| Module | Key Things to Check |
|--------|---------------------|
| A (Account) | Cookie/token encryption, OAuth flow, device fingerprint uniqueness |
| B (Knowledge) | Chunk size ≤512 tokens with 50-token overlap, RAG weight adjustment math |
| C (Content) | Risk scan before publish, cover rendering, schedule confirmation |
| D (Interaction) | Intent classification threshold (0.7), HITL trigger conditions |
| E (Risk) | Rate limits enforced (≤20 replies/hr, ≤50 DMs/hr), dedup logic |
| F (Analytics) | Data export format, merchant_id isolation |
