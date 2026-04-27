"""Playwright RPA 基础工具 — HumanizedBrowserContext。

提供账号级别的 Browser Context 复用、人类行为随机化、以及 Captcha 检测。
所有 RPA 操作均通过此类实现，具备防检测能力。
"""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright

from app.core.security import decrypt


# ── Captcha 检测选择器 ──────────────────────────────────────────────────────


CAPTCHA_SELECTORS = [
    ".captcha-modal",
    "#captcha-container",
    ".xhs-captcha",
    ".geetest_panel",
    ".dun-validate-container",
    ".nc_wrapper",
    "#captcha",
]


# ── 人类行为延迟 ─────────────────────────────────────────────────────────────


async def humanized_delay(
    min_seconds: float = 3.0,
    max_seconds: float = 15.0,
) -> float:
    """返回随机等待秒数，模拟人类操作间隔。

    Args:
        min_seconds: 最小秒数。
        max_seconds: 最大秒数。

    Returns:
        随机等待秒数。
    """
    return random.uniform(min_seconds, max_seconds)


async def human_scroll(page: Page) -> None:
    """模拟人类滚动页面：分步滚动，每步之间有随机延迟。

    避免一次性滚到底，减少被检测风险。
    """
    steps = random.randint(2, 4)
    for _ in range(steps):
        delta = random.randint(200, 500)
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.5, 1.5))


async def human_click(page: Page, selector: str) -> None:
    """模拟人类点击：先悬停，带随机偏移，再点击。

    Args:
        page: Playwright Page 对象。
        selector: CSS 选择器。
    """
    await page.hover(selector)
    await asyncio.sleep(random.uniform(0.2, 0.6))

    # 获取元素 bounding box，添加随机偏移
    box = await page.locator(selector).bounding_box()
    if box:
        offset_x = random.randint(-3, 3)
        offset_y = random.randint(-3, 3)
        click_x = box["x"] + box["width"] / 2 + offset_x
        click_y = box["y"] + box["height"] / 2 + offset_y
        await page.mouse.click(click_x, click_y)
    else:
        await page.click(selector)


async def human_hover(page: Page, selector: str) -> None:
    """模拟人类悬停：悬停后随机等待。

    Args:
        page: Playwright Page 对象。
        selector: CSS 选择器。
    """
    await page.hover(selector)
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def human_type(
    page: Page,
    selector: str,
    text: str,
    delay_ms: int | None = None,
) -> None:
    """模拟人类输入：逐字输入，每字之间有随机延迟。

    Args:
        page: Playwright Page 对象。
        selector: 输入框 CSS 选择器。
        text: 要输入的文本。
        delay_ms: 每个字符延迟（毫秒），不指定则随机 50~150ms。
    """
    await page.click(selector)
    await asyncio.sleep(random.uniform(0.1, 0.3))

    if delay_ms is None:
        delay_ms = random.randint(50, 150)

    for char in text:
        await page.keyboard.type(char, delay=delay_ms)
        await asyncio.sleep(random.uniform(0.01, 0.03))


async def check_captcha(page: Page) -> bool:
    """检测页面是否出现小红书验证码。

    Args:
        page: Playwright Page 对象。

    Returns:
        True 表示检测到验证码。
    """
    for selector in CAPTCHA_SELECTORS:
        try:
            if await page.is_visible(selector, timeout=2000):
                return True
        except Exception:
            pass
    return False


# ── Browser Context 管理 ──────────────────────────────────────────────────────


class HumanizedBrowserContext:
    """人类化的浏览器上下文管理器。

    每个账号复用同一个 Browser Context，保证设备指纹一致性。
    Context 按 account_id 缓存，避免频繁创建销毁。

    使用方式：
    ```python
    async with HumanizedBrowserContext(account_id="xxx") as ctx:
        page = await ctx.get_page()
        await page.goto("https://www.xiaohongshu.com/...")
    ```
    """

    _contexts: dict[str, BrowserContext] = {}
    _playwright: Playwright | None = None
    _browser: Browser | None = None

    def __init__(
        self,
        account_id: str,
        cookie: str | None = None,
        proxy_url: str | None = None,
        user_agent: str | None = None,
        viewport: tuple[int, int] = (1920, 1080),
        timezone: str = "Asia/Shanghai",
    ) -> None:
        """初始化人类化浏览器上下文。

        Args:
            account_id: 账号 ID（用于 Context 缓存 key）。
            cookie: 解密后的小红书 Cookie。
            proxy_url: 代理 URL（解密后）。
            user_agent: User-Agent 字符串。
            viewport: 视口大小。
            timezone: 时区。
        """
        self.account_id = account_id
        self.cookie = cookie
        self.proxy_url = proxy_url
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.viewport = viewport
        self.timezone = timezone
        self._page: Page | None = None

    @classmethod
    async def _get_playwright(cls) -> Playwright:
        """获取或初始化 Playwright 实例。"""
        if cls._playwright is None:
            cls._playwright = await import_playwright().start()
        return cls._playwright

    @classmethod
    async def _get_browser(cls) -> Browser:
        """获取或初始化 Browser 实例（headless=True）。"""
        if cls._browser is None:
            p = await cls._get_playwright()
            cls._browser = await p.chromium.launch(headless=True)
        return cls._browser

    async def __aenter__(self) -> "HumanizedBrowserContext":
        """进入异步上下文管理器，创建或复用 Browser Context。"""
        browser = await self._get_browser()

        # 尝试复用已有 Context
        if self.account_id in self._contexts:
            self._context = self._contexts[self.account_id]
        else:
            # 创建新 Context
            context_options: dict[str, Any] = {
                "viewport": {"width": self.viewport[0], "height": self.viewport[1]},
                "timezone_id": self.timezone,
                "user_agent": self.user_agent,
                "locale": "zh-CN",
                "ignore_https_errors": True,
            }

            # 设置代理
            if self.proxy_url:
                context_options["proxy"] = {"url": self.proxy_url}

            self._context = await browser.new_context(**context_options)

            # 注入 Cookie
            if self.cookie:
                import json

                try:
                    cookies = json.loads(self.cookie)
                    if isinstance(cookies, list):
                        await self._context.add_cookies(cookies)
                    elif isinstance(cookies, dict):
                        # 兼容单 dict 格式
                        await self._context.add_cookies([cookies])
                except (json.JSONDecodeError, TypeError):
                    pass

            self._contexts[self.account_id] = self._context

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出时不清除 Context（复用），仅关闭 Page。"""
        if self._page is not None:
            await self._page.close()
            self._page = None

    async def get_page(self) -> Page:
        """获取或创建一个新的 Page。"""
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
        return self._page

    @classmethod
    async def close_all(cls) -> None:
        """关闭所有 Context 和 Browser，清理资源。"""
        for ctx in cls._contexts.values():
            try:
                await ctx.close()
            except Exception:
                pass
        cls._contexts.clear()

        if cls._browser is not None:
            try:
                await cls._browser.close()
            except Exception:
                pass
            cls._browser = None

        if cls._playwright is not None:
            try:
                await cls._playwright.stop()
            except Exception:
                pass
            cls._playwright = None


async def import_playwright() -> Playwright:
    """延迟导入 playwright，避免未安装时影响其他功能。"""
    from playwright.async_api import async_playwright
    return async_playwright()


# ── 账号状态检查 ─────────────────────────────────────────────────────────────


async def check_account_status(account_id: str) -> str:
    """检查账号状态，拒绝向异常账号执行 RPA 操作。

    Args:
        account_id: 账号 ID。

    Returns:
        账号状态字符串。正常返回 "active"。
    """
    # TODO: 查询 accounts 表的 status 字段
    # from sqlalchemy import select
    # from app.models.account import Account
    # stmt = select(Account.status).where(Account.id == account_id)
    # result = await db.execute(stmt)
    # status = result.scalar_one_or_none()
    # return status or "unknown"
    return "active"
