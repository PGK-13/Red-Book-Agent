# Review PR

Review a pull request following the team code review workflow.

## Usage

```
/review-pr <pr-url-or-branch>
```

## Arguments

- `pr-url-or-branch`: GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`) or branch name (e.g., `feature/risk-module`)

## Workflow

### Step 1: Identify Module and Requirements

1. Run `gh pr view <pr-url>` to get PR details (title, body, branch, commits)
2. Read branch name and commit messages to identify which module is being implemented
3. Map to corresponding requirements file: `.kiro/specs/module-{letter}-{name}/requirements.md`
4. If module is unclear, ask the user

### Step 2: Fetch Code

```bash
gh pr diff <pr-url> > /tmp/pr_diff.txt
```

### Step 3: Requirements Coverage Analysis

For each acceptance criterion in the requirements file:
- Read the corresponding code that should implement it
- Verify implementation exists and is correct
- Check for missing edge cases, error handling, data isolation (merchant_id), sensitive field encryption

### Step 4: Code Quality Check

- Layering violations (business logic in routes? raw SQL in services?)
- Type annotations present and correct
- Security: encrypted fields use `_enc` suffix, no hardcoded secrets
- API conventions: response format, error codes, cursor pagination

### Step 5: Post Review Comments

**CRITICAL: Every bug must be posted as a SEPARATE PR review comment using GitHub's suggestion syntax.**

Use `gh api repos/OWNER/REPO/pulls/NUMBER/reviews` to post reviews.

```bash
gh api repos/OWNER/REPO/pulls/NUMBER/reviews --method POST --input - <<'EOF'
{
  "event": "COMMENT",
  "body": "## [Bug 1] <title>\n\n<description>\n\n**File**: <path>:<line>\n\n```suggestion\n<correct code>\n```",
  "comments": [{
    "path": "<file>",
    "line": <line>,
    "side": "RIGHT",
    "body": "```suggestion\n<correct code>\n```"
  }]
}
EOF
```

### Review Focus Areas by Module

| Module | Key Things to Check |
|--------|---------------------|
| A (Account) | Cookie/token encryption, OAuth flow, device fingerprint uniqueness |
| B (Knowledge) | Chunk size ≤512 tokens with 50-token overlap, RAG weight adjustment math |
| C (Content) | Risk scan before publish, cover rendering, schedule confirmation |
| D (Interaction) | Intent classification threshold (0.7), HITL trigger conditions |
| E (Risk) | Rate limits enforced (≤20 replies/hr, ≤50 DMs/hr), dedup logic |
| F (Analytics) | Data export format, merchant_id isolation |

### Verdict

Respond with one of:
- ✅ **Pass** — all requirements met, no blocking issues
- ⚠️ **Needs Changes** — blocking issues exist, must fix before merge
- ❌ **Block** — critical security/correctness issues
