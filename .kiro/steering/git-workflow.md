---
inclusion: fileMatch
fileMatchPattern: "**/.github/**,**/CHANGELOG*,**/CONTRIBUTING*"
---

# Git 工作流规范

## 分支策略

```
main          # 生产环境，只接受来自 develop 的 PR
develop       # 集成分支，功能开发完成后合并至此
feature/*     # 新功能
fix/*         # Bug 修复
chore/*       # 依赖更新、配置变更、文档等
```

## 分支命名

```
feature/account-oauth-login
fix/cookie-expiry-notification
chore/upgrade-langchain-0.2
```

## Commit Message

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

[可选 body]
```

type 取值：

| type | 含义 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档变更 |
| refactor | 重构（不影响功能） |
| test | 测试相关 |
| chore | 构建/依赖/配置 |
| perf | 性能优化 |

示例：

```
feat(account): 新增 OAuth 2.0 授权回调接口

支持小红书官方 OAuth 接入方式，token 加密存储至 accounts 表。
```

## PR 规范

- PR 标题格式与 commit message 一致
- 必须关联对应 Issue 或需求
- 需至少 1 人 Code Review 通过后合并
- 合并方式统一使用 Squash Merge，保持 main/develop 提交历史整洁
- PR 描述使用 `.github/pull_request_template.md` 模板
