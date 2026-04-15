# Security Rules

When working with files matching `**/core/security*,**/auth*,**/dependencies*,**/*token*,**/*encrypt*,**/*secret*`, follow these rules:

## Sensitive Data Handling
- OAuth tokens, Cookies, and Proxy URLs **must** be encrypted using `core/security.py`
- Encrypted fields use `_enc` suffix naming convention (e.g., `oauth_token_enc`, `cookie_enc`)
- Never log, print, or include raw tokens/secrets in error messages or responses
- Private keys and encryption materials **must not** be stored in the database, logged, or transmitted over the network

## Authentication
- All `/api/v1/` endpoints require JWT authentication via `dependencies.py:get_current_merchant`
- Webhook endpoints use HMAC signature verification for source legitimacy
- Provider callbacks (e.g., Xiaohongshu webhooks) must be deduplicated by platform IDs (`xhs_comment_id`, `xhs_note_id`)

## Environment Variables
- All secrets via environment variables only — no hardcoding
- Use `app/config.py` settings for configuration access
- Local dev uses `.env` (gitignored), reference `infra/.env.example`
