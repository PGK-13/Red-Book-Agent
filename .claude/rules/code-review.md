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

## Step 5: Post Review Comment

Use `gh pr comment` to post results on the PR:

```
## Review Results: <Module> — <Feature>

### Requirements Coverage
- [x] <criterion ref>: <what was verified>
- [ ] <criterion ref>: <issue>

### Code Quality
- <issue if any>

### Suggestions
- <optional improvement ideas>

### Verdict
✅ Pass / ⚠️ Needs Changes / ❌ Block
```

## Review Focus Areas by Module

| Module | Key Things to Check |
|--------|---------------------|
| A (Account) | Cookie/token encryption, OAuth flow, device fingerprint uniqueness |
| B (Knowledge) | Chunk size ≤512 tokens with 50-token overlap, RAG weight adjustment math |
| C (Content) | Risk scan before publish, cover rendering, schedule confirmation |
| D (Interaction) | Intent classification threshold (0.7), HITL trigger conditions |
| E (Risk) | Rate limits enforced (≤20 replies/hr, ≤50 DMs/hr), dedup logic |
| F (Analytics) | Data export format, merchant_id isolation |
