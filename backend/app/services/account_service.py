"""账号管理业务逻辑 — AccountService。

所有业务逻辑集中在此 Service 层，API 路由层只做参数校验和响应封装。
所有查询严格按 merchant_id 过滤，确保商家数据隔离。
敏感字段通过 core/security 加密/解密，原始凭证仅在内存中短暂存在。
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.notifications import send_alert
from app.core.rate_limiter import get_redis
from app.core.security import decrypt, encrypt
from app.models.account import Account, AccountPersona, ProxyConfig
from app.schemas.account import (
    AccountCreateRequest,
    PersonaUpdateRequest,
    ProxyUpdateRequest,
)

logger = logging.getLogger(__name__)

# 商家默认账号数量上限（可由套餐配置覆盖）
DEFAULT_ACCOUNT_LIMIT = 50

_MAC_CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


# ── 3.1 账号 CRUD ──


async def list_accounts(
    merchant_id: str,
    limit: int,
    cursor: str | None,
    db: AsyncSession,
) -> tuple[list[Account], str | None, bool]:
    """获取商家账号列表（cursor 分页）。

    Args:
        merchant_id: 商家 ID。
        limit: 每页数量。
        cursor: 分页游标（上一页最后一条记录的 id）。
        db: 数据库会话。

    Returns:
        (账号列表, 下一页游标, 是否还有更多)。
    """
    stmt = (
        select(Account)
        .where(Account.merchant_id == merchant_id)
        .options(selectinload(Account.persona), selectinload(Account.proxy_config))
        .order_by(Account.created_at.desc())
    )
    if cursor:
        stmt = stmt.where(Account.id < cursor)
    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = items[-1].id if has_more and items else None
    return items, next_cursor, has_more


async def _launch_browser(pw: object):
    """启动可用的 Chromium 浏览器。

    在本机优先复用已安装的 Google Chrome，避免依赖 Playwright 自带浏览器。
    """
    chromium = getattr(pw, "chromium")

    if _MAC_CHROME_PATH.exists():
        try:
            return await chromium.launch(headless=False, channel="chrome")
        except Exception:
            logger.debug("Falling back to bundled Chromium after channel=chrome failed")

    return await chromium.launch(headless=False)


async def create_account(
    merchant_id: str,
    data: AccountCreateRequest,
    db: AsyncSession,
) -> Account:
    """创建新账号。

    Args:
        merchant_id: 商家 ID。
        data: 账号创建请求。
        db: 数据库会话。

    Returns:
        新创建的 Account 对象。

    Raises:
        HTTPException: 账号数量超限或小红书用户 ID 已存在。
    """
    # 检查商家账号数量上限
    count_stmt = (
        select(func.count())
        .select_from(Account)
        .where(Account.merchant_id == merchant_id)
    )
    result = await db.execute(count_stmt)
    current_count = result.scalar_one()
    if current_count >= DEFAULT_ACCOUNT_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"账号数量已达上限 ({DEFAULT_ACCOUNT_LIMIT})",
        )

    account = Account(
        id=str(uuid4()),
        merchant_id=merchant_id,
        xhs_user_id=data.xhs_user_id,
        nickname=data.nickname,
        access_type=data.access_type,
        status="active",
    )
    db.add(account)
    await db.flush()
    await db.refresh(account, ["persona", "proxy_config"])
    return account


async def get_account(
    merchant_id: str,
    account_id: str,
    db: AsyncSession,
) -> Account:
    """获取单个账号详情。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        db: 数据库会话。

    Returns:
        Account 对象。

    Raises:
        HTTPException: 账号不存在。
    """
    stmt = (
        select(Account)
        .where(
            and_(
                Account.merchant_id == merchant_id,
                Account.id == account_id,
            )
        )
        .options(selectinload(Account.persona), selectinload(Account.proxy_config))
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在",
        )
    return account


async def delete_account(
    merchant_id: str,
    account_id: str,
    db: AsyncSession,
) -> None:
    """删除账号（级联删除 persona、proxy_config）。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        db: 数据库会话。

    Raises:
        HTTPException: 账号不存在。
    """
    account = await get_account(merchant_id, account_id, db)
    await db.delete(account)
    await db.flush()


# ── 3.2 OAuth 授权回调和 Cookie 管理 ──


async def handle_oauth_callback(
    merchant_id: str,
    account_id: str,
    code: str,
    db: AsyncSession,
) -> None:
    """处理 OAuth 2.0 授权回调。

    用授权码换取 access_token，加密后存入 oauth_token_enc。
    原始 token 仅在内存中短暂存在，不写入日志。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        code: OAuth 授权码。
        db: 数据库会话。
    """
    account = await get_account(merchant_id, account_id, db)

    # TODO: 实际调用小红书 OAuth API 换取 access_token
    # 此处模拟：code 即为 access_token（生产环境需替换为真实 HTTP 调用）
    access_token = code

    account.oauth_token_enc = encrypt(access_token)
    account.status = "active"
    await db.flush()


async def update_cookie(
    merchant_id: str,
    account_id: str,
    raw_cookie: str,
    expires_at: datetime,
    db: AsyncSession,
) -> None:
    """更新账号 Cookie。

    加密 raw_cookie 存入 cookie_enc，更新 cookie_expires_at。
    若账号状态为 auth_expired 则恢复为 active。
    原始 Cookie 仅在内存中短暂存在，不写入日志。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        raw_cookie: 原始 Cookie 字符串。
        expires_at: Cookie 过期时间。
        db: 数据库会话。
    """
    account = await get_account(merchant_id, account_id, db)

    account.cookie_enc = encrypt(raw_cookie)
    account.cookie_expires_at = expires_at

    if account.status == "auth_expired":
        account.status = "active"
        logger.info("Account %s restored to active after cookie refresh", account_id)

    await db.flush()


# ── 3.3 人设配置和代理配置 ──


async def update_persona(
    merchant_id: str,
    account_id: str,
    data: PersonaUpdateRequest,
    db: AsyncSession,
) -> AccountPersona:
    """创建或更新账号人设配置（upsert）。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        data: 人设更新请求。
        db: 数据库会话。

    Returns:
        更新后的 AccountPersona 对象。
    """
    account = await get_account(merchant_id, account_id, db)

    if account.persona is None:
        persona = AccountPersona(
            id=str(uuid4()),
            account_id=account.id,
        )
        db.add(persona)
        await db.flush()
        # 重新加载关系
        await db.refresh(account, ["persona"])
        # refresh 后 account.persona 不为空，但 mypy 需要显式断言
        persona = account.persona  # type: ignore[assignment]
        assert persona is not None
    else:
        persona = account.persona

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(persona, field, value)

    await db.flush()
    return persona


async def _check_fingerprint_uniqueness(
    merchant_id: str,
    account_id: str,
    user_agent: str,
    screen_resolution: str,
    timezone_val: str,
    db: AsyncSession,
) -> None:
    """校验设备指纹唯一性。

    同一商家下，user_agent + screen_resolution + timezone 组合不得重复。

    Raises:
        HTTPException: 设备指纹与同商家其他账号重复。
    """
    stmt = (
        select(ProxyConfig)
        .join(Account, Account.id == ProxyConfig.account_id)
        .where(
            and_(
                Account.merchant_id == merchant_id,
                ProxyConfig.account_id != account_id,
                ProxyConfig.user_agent == user_agent,
                ProxyConfig.screen_resolution == screen_resolution,
                ProxyConfig.timezone == timezone_val,
            )
        )
    )
    result = await db.execute(stmt)
    duplicate = result.scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="设备指纹（user_agent + screen_resolution + timezone）与同商家其他账号重复",
        )


async def update_proxy(
    merchant_id: str,
    account_id: str,
    data: ProxyUpdateRequest,
    db: AsyncSession,
) -> ProxyConfig:
    """创建或更新代理配置（upsert）。

    proxy_url 加密存储。校验设备指纹唯一性。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        data: 代理更新请求。
        db: 数据库会话。

    Returns:
        更新后的 ProxyConfig 对象。

    Raises:
        HTTPException: 设备指纹重复。
    """
    account = await get_account(merchant_id, account_id, db)

    # 校验设备指纹唯一性
    await _check_fingerprint_uniqueness(
        merchant_id,
        account_id,
        data.user_agent,
        data.screen_resolution,
        data.timezone,
        db,
    )

    if account.proxy_config is None:
        proxy = ProxyConfig(
            id=str(uuid4()),
            account_id=account.id,
            proxy_url=encrypt(data.proxy_url),
            user_agent=data.user_agent,
            screen_resolution=data.screen_resolution,
            timezone=data.timezone,
            is_active=data.is_active,
        )
        db.add(proxy)
        await db.flush()
        await db.refresh(account, ["proxy_config"])
        # refresh 后 proxy_config 不为空，但 mypy 需要显式断言
        updated_proxy = account.proxy_config
        assert updated_proxy is not None
        return updated_proxy

    proxy = account.proxy_config
    proxy.proxy_url = encrypt(data.proxy_url)
    proxy.user_agent = data.user_agent
    proxy.screen_resolution = data.screen_resolution
    proxy.timezone = data.timezone
    proxy.is_active = data.is_active
    await db.flush()
    return proxy


# ── 3.4 账号状态探测 ──


async def probe_account_status(
    account_id: str,
    db: AsyncSession,
) -> str:
    """探测单个账号状态。

    检测 Cookie 过期时间和平台返回状态码：
    - Cookie 距过期 < 24h → 发送预警通知
    - Cookie 已过期 → 状态设为 auth_expired
    - 平台 403/封禁 → 状态设为 banned
    - 平台 429/限流 → 状态设为 suspended

    Args:
        account_id: 账号 ID。
        db: 数据库会话。

    Returns:
        探测后的账号状态字符串。
    """
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account is None:
        logger.error("Probe failed: account %s not found", account_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在",
        )

    now = datetime.now(timezone.utc)
    original_status = account.status

    # 检测 Cookie 过期
    if account.cookie_expires_at is not None:
        remaining = account.cookie_expires_at - now
        if remaining <= timedelta(0):
            # Cookie 已过期
            account.status = "auth_expired"
            logger.warning(
                "Account %s cookie expired at %s, status → auth_expired",
                account_id,
                account.cookie_expires_at.isoformat(),
            )
            await send_alert(
                merchant_id=account.merchant_id,
                alert_type="cookie_expired",
                message=f"账号 {account.nickname} 的 Cookie 已过期，自动化操作已暂停",
                severity="critical",
            )
        elif remaining < timedelta(hours=24):
            # Cookie 即将过期（< 24h）
            hours_left = remaining.total_seconds() / 3600
            logger.info(
                "Account %s cookie expires in %.1f hours, sending warning",
                account_id,
                hours_left,
            )
            await send_alert(
                merchant_id=account.merchant_id,
                alert_type="cookie_expiring",
                message=f"账号 {account.nickname} 的 Cookie 将在 {hours_left:.1f} 小时后过期，请及时刷新",
                severity="warning",
            )

    # 模拟平台状态码检测
    # TODO: 实际调用小红书 API 检测账号状态，此处预留接口
    platform_status_code = await _check_platform_status(account)
    if platform_status_code == 403:
        account.status = "banned"
        logger.error(
            "Account %s received 403 from platform, status → banned (ts=%s)",
            account_id,
            now.isoformat(),
        )
        await send_alert(
            merchant_id=account.merchant_id,
            alert_type="account_banned",
            message=f"账号 {account.nickname} 被平台封禁（错误码 403），请人工处理",
            severity="critical",
        )
    elif platform_status_code == 429:
        account.status = "suspended"
        logger.warning(
            "Account %s received 429 from platform, status → suspended (ts=%s)",
            account_id,
            now.isoformat(),
        )
        await send_alert(
            merchant_id=account.merchant_id,
            alert_type="account_rate_limited",
            message=f"账号 {account.nickname} 被平台限流（错误码 429），操作已暂停",
            severity="warning",
        )

    account.last_probed_at = now
    await db.flush()

    if account.status != original_status:
        logger.info(
            "Account %s status changed: %s → %s",
            account_id,
            original_status,
            account.status,
        )

    return account.status


async def _check_platform_status(account: Account) -> int | None:
    """检测平台返回的状态码。

    TODO: 实际实现需调用小红书 API 或通过 Playwright 检测。
    当前返回 None 表示正常。

    Args:
        account: 账号对象。

    Returns:
        平台状态码，None 表示正常。
    """
    return None


async def probe_all_accounts(db: AsyncSession) -> list[dict[str, str]]:
    """探测所有活跃账号状态。

    查询所有 active 状态的账号，逐个调用 probe_account_status。

    Args:
        db: 数据库会话。

    Returns:
        探测结果列表 [{account_id, status}]。
    """
    stmt = select(Account).where(Account.status == "active")
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    results: list[dict[str, str]] = []
    for account in accounts:
        try:
            new_status = await probe_account_status(account.id, db)
            results.append({"account_id": account.id, "status": new_status})
        except Exception:
            logger.exception(
                "Failed to probe account %s (ts=%s)",
                account.id,
                datetime.now(timezone.utc).isoformat(),
            )
            results.append({"account_id": account.id, "status": "error"})

    return results


# ── 3.5 账号画像同步 ──


async def sync_profile(
    merchant_id: str,
    account_id: str,
    db: AsyncSession,
) -> AccountPersona:
    """通过 Playwright 抓取小红书个人主页，同步账号画像。

    提取昵称、简介、标签、粉丝数，更新 account_personas 表。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        db: 数据库会话。

    Returns:
        更新后的 AccountPersona 对象。
    """
    account = await get_account(merchant_id, account_id, db)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright is not installed, cannot sync profile")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playwright 未安装，无法同步画像",
        )

    async with async_playwright() as pw:
        browser = await _launch_browser(pw)
        try:
            context = await _create_browser_context(browser, account, db)
            page = await context.new_page()  # type: ignore[attr-defined]

            profile_url = (
                f"https://www.xiaohongshu.com/user/profile/{account.xhs_user_id}"
            )
            await page.goto(profile_url, wait_until="networkidle")

            # 提取画像数据
            nickname = await _safe_text(page, ".user-nickname") or account.nickname
            bio = await _safe_text(page, ".user-desc") or ""
            tags = await _extract_tags(page)
            follower_count = await _extract_follower_count(page)

            # 更新账号昵称
            account.nickname = nickname

            # Upsert persona
            now = datetime.now(timezone.utc)
            if account.persona is None:
                persona = AccountPersona(
                    id=str(uuid4()),
                    account_id=account.id,
                    bio=bio,
                    tags=tags,
                    follower_count=follower_count,
                    profile_synced_at=now,
                )
                db.add(persona)
            else:
                account.persona.bio = bio
                account.persona.tags = tags
                account.persona.follower_count = follower_count
                account.persona.profile_synced_at = now

            await db.flush()
            await db.refresh(account, ["persona"])

            logger.info("Profile synced for account %s", account_id)
            synced = account.persona
            assert synced is not None
            return synced

        finally:
            await browser.close()  # type: ignore[attr-defined]


async def _safe_text(page: object, selector: str) -> str | None:
    """安全提取页面元素文本。"""
    try:
        element = await page.query_selector(selector)  # type: ignore[attr-defined]
        if element:
            return (await element.text_content() or "").strip()
    except Exception:
        pass
    return None


async def _extract_tags(page: object) -> list[str]:
    """提取用户标签列表。"""
    try:
        elements = await page.query_selector_all(".user-tag")  # type: ignore[attr-defined]
        tags: list[str] = []
        for el in elements:
            text = await el.text_content()
            if text and text.strip():
                tags.append(text.strip())
        return tags
    except Exception:
        return []


async def _extract_follower_count(page: object) -> int | None:
    """提取粉丝数。"""
    try:
        text = await _safe_text(page, ".follower-count")  # type: ignore[arg-type]
        if text:
            # 处理 "1.2万" 等格式
            cleaned = text.replace(",", "").strip()
            if "万" in cleaned:
                return int(float(cleaned.replace("万", "")) * 10000)
            return int(cleaned)
    except (ValueError, TypeError):
        pass
    return None


# ── 3.6 Playwright 浏览器上下文管理 ──


def _parse_resolution(resolution: str) -> dict[str, int]:
    """解析屏幕分辨率字符串为 viewport 字典。

    Args:
        resolution: 格式 "1920x1080"。

    Returns:
        {"width": 1920, "height": 1080}。
    """
    parts = resolution.split("x")
    return {"width": int(parts[0]), "height": int(parts[1])}


def _parse_cookies(cookie_str: str, domain: str = ".xiaohongshu.com") -> list[dict]:
    """解析 Cookie 字符串为 Playwright cookie 列表。

    Args:
        cookie_str: 原始 Cookie 字符串（"key1=val1; key2=val2" 格式）。
        domain: Cookie 所属域名。

    Returns:
        Playwright add_cookies 所需的 cookie 字典列表。
    """
    cookies: list[dict] = []
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookies.append(
            {
                "name": name.strip(),
                "value": value.strip(),
                "domain": domain,
                "path": "/",
            }
        )
    return cookies


async def _create_browser_context(
    browser: object,
    account: Account,
    db: AsyncSession,
) -> object:
    """根据 ProxyConfig 创建隔离的 Playwright BrowserContext。

    配置 proxy、user_agent、viewport、timezone_id，注入解密后的 Cookie。
    未配置代理时记录警告日志（IP 混用风险）。
    上下文按需创建，使用完毕后由调用方关闭。

    Args:
        browser: Playwright Browser 实例。
        account: 账号对象（需已加载 proxy_config 关系）。
        db: 数据库会话。

    Returns:
        Playwright BrowserContext 实例。
    """
    context_kwargs: dict = {}

    # 加载代理配置
    if account.proxy_config and account.proxy_config.is_active:
        proxy_url = decrypt(account.proxy_config.proxy_url)
        context_kwargs["proxy"] = {"server": proxy_url}
        context_kwargs["user_agent"] = account.proxy_config.user_agent
        context_kwargs["viewport"] = _parse_resolution(
            account.proxy_config.screen_resolution
        )
        context_kwargs["timezone_id"] = account.proxy_config.timezone
    else:
        logger.warning(
            "Account %s has no active proxy config — IP mixing risk",
            account.id,
        )

    context = await browser.new_context(**context_kwargs)  # type: ignore[attr-defined]

    # 注入解密后的 Cookie
    if account.cookie_enc:
        raw_cookie = decrypt(account.cookie_enc)
        cookies = _parse_cookies(raw_cookie)
        if cookies:
            await context.add_cookies(cookies)  # type: ignore[union-attr]

    return context


async def get_browser_context(
    account_id: str,
    db: AsyncSession,
) -> object:
    """获取账号的隔离 Playwright 浏览器上下文。

    按需创建，调用方负责在使用完毕后关闭 context 和 browser。

    Args:
        account_id: 账号 ID。
        db: 数据库会话。

    Returns:
        (browser, context) 元组。调用方需关闭 browser。
    """
    stmt = (
        select(Account)
        .where(Account.id == account_id)
        .options(selectinload(Account.proxy_config))
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在",
        )

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playwright 未安装",
        )

    pw = await async_playwright().start()
    browser = await _launch_browser(pw)
    context = await _create_browser_context(browser, account, db)
    return browser, context


# ── 3.7 扫码登录 ──

QR_SESSION_TTL = 300  # 5 分钟
QR_SESSION_PREFIX = "qr_session:"
PUB_QR_SESSION_PREFIX = "pub_qr_session:"
XHS_LOGIN_URL = "https://www.xiaohongshu.com"

# 二维码区域选择器（小红书主站登录弹窗中的二维码）
QR_CODE_IMG_SELECTOR = ".code-area"
# 扫码成功后的遮盖提示文字（QR 区被白色遮盖，上层显示此文字）
QR_SCAN_SUCCESS_SELECTOR = ".code-area .scan-success, .login-modal .success-text"

# 登录成功检测选择器
LOGIN_MODAL_SELECTOR = ".login-modal"
LOGIN_SUCCESS_SELECTOR = ".user-avatar, .reds-avatar"

# 验证码弹窗检测选择器（小红书扫码确认后可能弹出的短信验证码模态框）
# 优先通过弹窗标题文字定位，比 input 选择器更可靠，不会误匹配登录页手机号输入框
CAPTCHA_DIALOG_SELECTOR = (
    # 包含"短信验证码"或"验证码验证"文字的弹窗标题
    "div:text('短信验证码'), "
    "span:text('短信验证码'), "
    "h3:text('短信验证码'), "
    "p:text('短信验证码'), "
    # 包含"验证码将发送至"提示文字
    "div:text('验证码将发送至'), "
    "span:text('验证码将发送至'), "
    "p:text('验证码将发送至')"
)

# 验证码输入框选择器（在确认弹窗存在后使用）
CAPTCHA_INPUT_SELECTOR = (
    "input[placeholder*='验证码'], "
    "input[placeholder*='请输入验证码'], "
    "input[type='tel'][maxlength='6'], "
    "input[type='number'][maxlength='6'], "
    "input.captcha-input"
)
CAPTCHA_SUBMIT_SELECTOR = (
    "button:text('验证'), "
    "button:text('确认'), "
    "button:text('提交'), "
    "button.captcha-submit, "
    "button[class*='submit'], "
    ".captcha-container button"
)

# 公开扫码会话的进程内 Playwright 引用缓存
# 结构: {session_id: {"pw_instance": ..., "browser": ..., "context": ..., "page": ...}}
_active_pub_qr_sessions: dict[str, dict] = {}


async def start_qr_login(
    merchant_id: str,
    account_id: str,
    db: AsyncSession,
) -> dict[str, str]:
    """启动扫码登录，返回二维码图片和 session_id。

    通过 Playwright 打开小红书登录页，截取二维码区域为 base64 图片。
    在 Redis 中创建扫码会话（TTL=5min）。

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        db: 数据库会话。

    Returns:
        {"session_id": str, "qr_image_base64": str}。
    """
    account = await get_account(merchant_id, account_id, db)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playwright 未安装",
        )

    pw_instance = await async_playwright().start()
    browser = await _launch_browser(pw_instance)
    context = await _create_browser_context(browser, account, db)
    page = await context.new_page()  # type: ignore[attr-defined]

    try:
        await page.goto(XHS_LOGIN_URL, wait_until="networkidle")

        # 截取二维码区域
        qr_element = await page.query_selector(".qrcode-img, .login-qrcode img, canvas")
        if qr_element:
            qr_bytes = await qr_element.screenshot()
        else:
            # 回退：截取整个页面
            qr_bytes = await page.screenshot()

        qr_image_base64 = base64.b64encode(qr_bytes).decode()

        # 创建 Redis 会话
        session_id = str(uuid4())
        redis = get_redis()
        session_data = json.dumps(
            {
                "account_id": account_id,
                "merchant_id": merchant_id,
                "status": "waiting",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        await redis.setex(
            f"{QR_SESSION_PREFIX}{session_id}",
            QR_SESSION_TTL,
            session_data,
        )

        # 注意：browser/context 保持打开，由 poll 阶段关闭
        # 将 browser 引用存入 Redis 无法序列化，实际生产中需使用
        # 浏览器上下文池或进程内缓存。此处简化处理：关闭 context，
        # poll 时重新创建。
        await context.close()  # type: ignore[attr-defined]
        await browser.close()  # type: ignore[attr-defined]
        await pw_instance.stop()

        return {"session_id": session_id, "qr_image_base64": qr_image_base64}

    except Exception:
        await context.close()  # type: ignore[attr-defined]
        await browser.close()  # type: ignore[attr-defined]
        await pw_instance.stop()
        raise


async def poll_qr_login_status(
    merchant_id: str,
    account_id: str,
    session_id: str,
    db: AsyncSession,
) -> dict[str, str]:
    """轮询扫码登录状态。

    从 Redis 读取 session 状态，检测登录是否成功。
    - 登录成功 → 提取 Cookie，加密存入 cookie_enc
    - 超时（> 5min）→ 返回 expired

    Args:
        merchant_id: 商家 ID。
        account_id: 账号 ID。
        session_id: 扫码会话 ID。
        db: 数据库会话。

    Returns:
        {"status": "waiting" | "success" | "expired"}。
    """
    redis = get_redis()
    session_key = f"{QR_SESSION_PREFIX}{session_id}"
    raw = await redis.get(session_key)

    if raw is None:
        # Session 已过期（Redis TTL）
        return {"status": "expired"}

    session_data = json.loads(raw)

    # 验证 session 归属
    if session_data.get("account_id") != account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="会话不属于该账号",
        )

    # 检查是否已成功
    if session_data.get("status") == "success":
        return {"status": "success"}

    # 检查超时
    created_at = datetime.fromisoformat(session_data["created_at"])
    if datetime.now(timezone.utc) - created_at > timedelta(seconds=QR_SESSION_TTL):
        await redis.delete(session_key)
        return {"status": "expired"}

    # 尝试通过 Playwright 检测登录状态
    account = await get_account(merchant_id, account_id, db)
    login_success = False
    extracted_cookies: str | None = None

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await _launch_browser(pw)
            try:
                context = await _create_browser_context(browser, account, db)
                page = await context.new_page()  # type: ignore[attr-defined]
                await page.goto(XHS_LOGIN_URL, wait_until="networkidle")

                # 检测登录成功标志：URL 变化或特定元素出现
                current_url = page.url
                if "login" not in current_url.lower() or await page.query_selector(
                    ".user-avatar, .creator-home"
                ):
                    login_success = True
                    # 提取所有 Cookie
                    cookies = await context.cookies()  # type: ignore[attr-defined]
                    cookie_parts = [f"{c['name']}={c['value']}" for c in cookies]
                    extracted_cookies = "; ".join(cookie_parts)

                await context.close()  # type: ignore[attr-defined]
            finally:
                await browser.close()  # type: ignore[attr-defined]

    except ImportError:
        logger.warning("Playwright not available for QR login polling")
    except Exception:
        logger.exception(
            "Error during QR login status check for session %s", session_id
        )

    if login_success and extracted_cookies:
        # 加密存储 Cookie
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        await update_cookie(merchant_id, account_id, extracted_cookies, expires_at, db)

        # 更新 Redis session 状态
        session_data["status"] = "success"
        remaining_ttl = await redis.ttl(session_key)
        if remaining_ttl > 0:
            await redis.setex(session_key, remaining_ttl, json.dumps(session_data))

        logger.info(
            "QR login success for account %s, session %s", account_id, session_id
        )
        return {"status": "success"}

    return {"status": "waiting"}


# ── 3.8 公开扫码登录（含验证码检测） ──


async def public_start_qr_login() -> dict[str, str]:
    """启动公开扫码登录，返回二维码图片和 session_id。

    通过 Playwright 打开小红书主站，截取登录弹窗中的二维码区域为 base64 图片。
    在 Redis 中创建公开扫码会话（TTL=5min），并将 Playwright 实例
    存入进程内缓存 ``_active_pub_qr_sessions`` 以便后续轮询复用。

    Returns:
        {"session_id": str, "qr_image_base64": str}
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playwright 未安装",
        )

    pw_instance = await async_playwright().start()
    browser = await _launch_browser(pw_instance)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    # 注入反自动化检测脚本
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        window.chrome = { runtime: {} };
    """)
    page = await context.new_page()

    try:
        await page.goto(XHS_LOGIN_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # 截取二维码区域（.code-area 是小红书登录弹窗中的二维码容器）
        qr_element = await page.query_selector(QR_CODE_IMG_SELECTOR)
        if qr_element:
            qr_bytes = await qr_element.screenshot()
        else:
            qr_bytes = await page.screenshot()

        qr_image_base64 = base64.b64encode(qr_bytes).decode()

        # 创建 Redis 会话
        session_id = str(uuid4())
        redis = get_redis()
        session_data = json.dumps(
            {
                "status": "waiting",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "token": None,
                "user": None,
            }
        )
        await redis.setex(
            f"{PUB_QR_SESSION_PREFIX}{session_id}",
            QR_SESSION_TTL,
            session_data,
        )

        # 将 Playwright 引用存入进程内缓存，轮询时复用
        _active_pub_qr_sessions[session_id] = {
            "pw_instance": pw_instance,
            "browser": browser,
            "context": context,
            "page": page,
        }

        logger.info("Public QR login started, session %s", session_id)
        return {"session_id": session_id, "qr_image_base64": qr_image_base64}

    except Exception:
        logger.exception("Failed to start public QR login")
        await page.close()
        await context.close()
        await browser.close()
        await pw_instance.stop()
        raise


async def public_poll_qr_login_status(session_id: str) -> dict:
    """轮询公开扫码登录状态（含验证码检测）。

    在检测登录成功之前，先检查页面是否存在验证码输入框。
    检测到验证码后，Redis 会话状态更新为 ``need_captcha``，
    Playwright 实例保持存活等待验证码提交。

    Args:
        session_id: 扫码会话 ID。

    Returns:
        {"status": str, "token": str | None, "user": dict | None}
    """
    redis = get_redis()
    session_key = f"{PUB_QR_SESSION_PREFIX}{session_id}"
    raw = await redis.get(session_key)

    if raw is None:
        _cleanup_pub_qr_session(session_id)
        return {"status": "expired", "token": None, "user": None}

    session_data = json.loads(raw)

    # 已检测到验证码，等待用户提交，直接返回
    if session_data.get("status") == "need_captcha":
        return {"status": "need_captcha", "token": None, "user": None}

    # 已登录成功，返回缓存的 token 和 user
    if session_data.get("status") == "success":
        return {
            "status": "success",
            "token": session_data.get("token"),
            "user": session_data.get("user"),
        }

    # status == "waiting"：通过 Playwright 检测登录状态
    pw_session = _active_pub_qr_sessions.get(session_id)
    if pw_session is None:
        print(f"[POLL] {session_id}: pw_session is None, returning waiting")
        return {"status": "waiting", "token": None, "user": None}

    page = pw_session["page"]
    context = pw_session["context"]
    try:
        current_url = page.url
        cookies = await context.cookies()
        cookie_names = [c["name"] for c in cookies]

        # 记录初始 cookie 快照（首次轮询时保存）
        initial_cookies = session_data.get("initial_cookie_names")
        if initial_cookies is None:
            session_data["initial_cookie_names"] = cookie_names
            remaining_ttl = await redis.ttl(session_key)
            if remaining_ttl > 0:
                await redis.setex(session_key, remaining_ttl, json.dumps(session_data))
            initial_cookies = cookie_names

        # 计算新增的 cookie
        new_cookies = [n for n in cookie_names if n not in initial_cookies]

        print(
            f"[POLL] {session_id}: url={current_url}, "
            f"cookies={len(cookies)}, new_cookies={new_cookies}"
        )

        # ── 验证码检测 ──
        captcha_detected = False

        # 冷却期：验证码提交后 15 秒内跳过验证码检测，只检测登录成功
        captcha_cooldown = False
        submitted_at_str = session_data.get("captcha_submitted_at")
        if submitted_at_str:
            submitted_at = datetime.fromisoformat(submitted_at_str)
            elapsed = (datetime.now(timezone.utc) - submitted_at).total_seconds()
            if elapsed < 15:
                captcha_cooldown = True
                print(f"[POLL] {session_id}: captcha cooldown, {elapsed:.0f}s since submit")

        if not captcha_cooldown:
            # 情况 1：被小红书反爬拦截，跳转到二次验证页面
            if "/website-login/captcha" in current_url:
                print(f"[POLL] {session_id}: anti-bot captcha page detected")
                captcha_detected = True

            # 情况 2：短信验证码弹窗（叠加在登录弹窗之上）
            if not captcha_detected:
                for p in context.pages:
                    try:
                        html_content = await p.content()
                        if "短信验证码验证" in html_content:
                            print(f"[POLL] {session_id}: SMS captcha dialog detected")
                            captcha_detected = True
                            break
                        if "验证码将发送至" in html_content:
                            print(f"[POLL] {session_id}: SMS captcha dialog detected (alt)")
                            captcha_detected = True
                            break
                    except Exception as e:
                        print(f"[POLL] {session_id}: page.content() error: {e}")

        if captcha_detected:
            session_data["status"] = "need_captcha"
            remaining_ttl = await redis.ttl(session_key)
            if remaining_ttl > 0:
                await redis.setex(
                    session_key, remaining_ttl, json.dumps(session_data)
                )
            print(f"[POLL] {session_id}: -> returning need_captcha")
            return {"status": "need_captcha", "token": None, "user": None}

        # ── 登录成功检测（多信号综合判断） ──
        logged_in = False

        # 信号 1：页面 URL 不再是初始登录页
        # 登录成功后小红书会跳转回 explore 页面（去掉登录弹窗）或个人主页
        initial_url = session_data.get("initial_url")
        if initial_url is None:
            session_data["initial_url"] = current_url
            remaining_ttl = await redis.ttl(session_key)
            if remaining_ttl > 0:
                await redis.setex(session_key, remaining_ttl, json.dumps(session_data))
            initial_url = current_url

        if "/user/" in current_url:
            print(f"[POLL] {session_id}: login detected via URL /user/")
            logged_in = True

        # 信号 2：页面 HTML 中出现登录后才有的元素
        if not logged_in:
            try:
                html = await page.content()
                login_indicators = ["退出登录", "side-bar-user", "user-info-box"]
                for indicator in login_indicators:
                    if indicator in html:
                        print(f"[POLL] {session_id}: login detected via HTML '{indicator}'")
                        logged_in = True
                        break
            except Exception:
                pass

        # 信号 3：新增了登录相关 cookie（对比初始快照）
        if not logged_in and new_cookies:
            login_cookie_candidates = [
                "customer-sso-sid", "access-token", "galaxy_creator_session_id",
                "xhsTrackerId", "extra_exp_ids", "id_token",
            ]
            new_login_cookies = [n for n in new_cookies if any(lc in n for lc in login_cookie_candidates)]
            if new_login_cookies:
                print(f"[POLL] {session_id}: login detected via new cookies: {new_login_cookies}")
                logged_in = True

        if logged_in:
            nickname = ""
            avatar_url: str | None = None
            xhs_user_id = ""

            # 如果还在 explore 页面，主动导航到"我的"页面获取用户信息
            if "/user/" not in current_url:
                try:
                    await page.goto(
                        "https://www.xiaohongshu.com/user/profile/self",
                        wait_until="domcontentloaded",
                        timeout=8000,
                    )
                    await page.wait_for_timeout(1000)
                    current_url = page.url
                    print(f"[POLL] {session_id}: navigated to profile, url={current_url}")
                except Exception as e:
                    print(f"[POLL] {session_id}: failed to navigate to profile: {e}")

            # 尝试从页面提取用户信息
            try:
                nickname = await _safe_text(
                    page,
                    ".user-name, .nickname, .side-bar-user .name, "
                    "[class*='username'], [class*='nick']"
                ) or ""
                avatar_el = await page.query_selector(
                    ".user-avatar img, .reds-avatar img, .avatar img, "
                    "[class*='avatar'] img"
                )
                if avatar_el:
                    avatar_url = await avatar_el.get_attribute("src")
            except Exception:
                pass

            if "/user/" in current_url:
                xhs_user_id = current_url.split("/user/")[-1].split("?")[0]

            # 签发 JWT
            from jose import jwt as jose_jwt

            from app.config import settings

            payload = {
                "sub": xhs_user_id or "xhs_user",
                "nickname": nickname or "小红书用户",
                "avatar": avatar_url,
                "exp": datetime.now(timezone.utc)
                + timedelta(minutes=settings.jwt_expire_minutes),
            }
            token = jose_jwt.encode(
                payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
            )

            user_info = {
                "nickname": nickname or "小红书用户",
                "avatar": avatar_url,
                "xhs_user_id": xhs_user_id or "xhs_user",
            }

            session_data["status"] = "success"
            session_data["token"] = token
            session_data["user"] = user_info
            remaining_ttl = await redis.ttl(session_key)
            if remaining_ttl > 0:
                await redis.setex(session_key, remaining_ttl, json.dumps(session_data))

            _cleanup_pub_qr_session(session_id)
            print(f"[POLL] {session_id}: -> returning success, nickname={nickname}")
            return {"status": "success", "token": token, "user": user_info}

    except Exception:
        logger.exception(
            "Error during public QR login status check for session %s",
            session_id,
        )
        _cleanup_pub_qr_session(session_id)
        return {"status": "expired", "token": None, "user": None}

    return {"status": "waiting", "token": None, "user": None}


async def public_submit_captcha(session_id: str, captcha: str) -> dict[str, str]:
    """在 Playwright 页面中填入验证码并提交。

    从 Redis 读取会话状态，仅在 ``need_captcha`` 状态下执行 Playwright
    操作：填入验证码、点击提交按钮（或模拟回车），然后将会话状态回退为
    ``waiting`` 以便后续轮询继续检测登录结果。

    Args:
        session_id: 扫码会话 ID。
        captcha: 6 位数字验证码。

    Returns:
        包含 ``status`` 键的字典。
    """
    redis = get_redis()
    session_key = f"{PUB_QR_SESSION_PREFIX}{session_id}"
    raw = await redis.get(session_key)

    if raw is None:
        return {"status": "expired"}

    session_data = json.loads(raw)

    if session_data.get("status") != "need_captcha":
        return {"status": session_data.get("status", "expired")}

    pw_session = _active_pub_qr_sessions.get(session_id)
    if pw_session is None:
        return {"status": "expired"}

    context = pw_session["context"]

    # 遍历所有页面，找到包含验证码输入框的页面
    captcha_page = None
    for p in context.pages:
        try:
            html = await p.content()
            if "短信验证码验证" in html or "验证码将发送至" in html or "请输入验证码" in html:
                captcha_page = p
                print(f"[CAPTCHA] {session_id}: found captcha page: {p.url}")
                break
        except Exception:
            pass

    if captcha_page is None:
        print(f"[CAPTCHA] {session_id}: no captcha page found")
        _cleanup_pub_qr_session(session_id)
        return {"status": "expired"}

    try:
        # 用 JavaScript 直接操作 DOM：查找输入框、填入验证码、点击提交
        # 这样避免 ElementHandle 引用失效的问题
        result = await captcha_page.evaluate(
            """(code) => {
                // 查找验证码输入框
                const inputs = document.querySelectorAll('input');
                let targetInput = null;
                for (const inp of inputs) {
                    const rect = inp.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;
                    const ph = (inp.placeholder || '');
                    if (ph.includes('验证码') || ph.includes('请输入')) {
                        targetInput = inp;
                        break;
                    }
                    // 6位数字输入框
                    if ((inp.maxLength >= 4 && inp.maxLength <= 6) && inp.type !== 'password') {
                        targetInput = inp;
                    }
                }
                if (!targetInput) return { ok: false, error: 'input not found' };

                // 模拟 React 受控组件的值设置
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                nativeInputValueSetter.call(targetInput, code);
                targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                targetInput.dispatchEvent(new Event('change', { bubbles: true }));

                // 查找提交按钮
                const buttons = document.querySelectorAll('button');
                let submitBtn = null;
                for (const btn of buttons) {
                    const text = (btn.textContent || '').trim();
                    const rect = btn.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;
                    if (text === '验证' || text === '确认' || text === '提交') {
                        submitBtn = btn;
                        break;
                    }
                }

                if (submitBtn) {
                    submitBtn.click();
                    return { ok: true, method: 'button_click' };
                }

                // 没找到按钮，尝试回车
                targetInput.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true
                }));
                return { ok: true, method: 'enter_key' };
            }""",
            captcha,
        )
        print(f"[CAPTCHA] {session_id}: JS fill result: {result}")

        if not result.get("ok"):
            # JS 方式失败，尝试 Playwright 原生方式作为兜底
            print(f"[CAPTCHA] {session_id}: JS failed, trying Playwright fill")
            await captcha_page.fill(CAPTCHA_INPUT_SELECTOR, captcha)
            await captcha_page.wait_for_timeout(300)
            submit_btn = await captcha_page.query_selector(CAPTCHA_SUBMIT_SELECTOR)
            if submit_btn:
                await submit_btn.click()
            else:
                await captcha_page.keyboard.press("Enter")

        await captcha_page.wait_for_timeout(2000)

        session_data["status"] = "waiting"
        session_data["captcha_submitted_at"] = datetime.now(timezone.utc).isoformat()
        remaining_ttl = await redis.ttl(session_key)
        if remaining_ttl > 0:
            await redis.setex(session_key, remaining_ttl, json.dumps(session_data))

        print(f"[CAPTCHA] {session_id}: captcha submitted, waiting for result")
        return {"status": "waiting"}

    except Exception:
        logger.exception(
            "Failed to submit captcha for public QR session %s", session_id
        )
        _cleanup_pub_qr_session(session_id)
        return {"status": "expired"}


def _cleanup_pub_qr_session(session_id: str) -> None:
    """清理公开扫码会话的 Playwright 资源。

    从 ``_active_pub_qr_sessions`` 中移除并关闭浏览器实例。
    静默处理所有异常，确保不会因清理失败而中断业务流程。

    Args:
        session_id: 扫码会话 ID。
    """
    pw_session = _active_pub_qr_sessions.pop(session_id, None)
    if pw_session is None:
        return
    try:
        import asyncio

        loop = asyncio.get_event_loop()
        page = pw_session.get("page")
        context = pw_session.get("context")
        browser = pw_session.get("browser")
        pw_instance = pw_session.get("pw_instance")
        if page:
            loop.create_task(page.close())
        if context:
            loop.create_task(context.close())
        if browser:
            loop.create_task(browser.close())
        if pw_instance:
            loop.create_task(pw_instance.stop())
    except Exception:
        logger.debug("Error cleaning up public QR session %s", session_id)
