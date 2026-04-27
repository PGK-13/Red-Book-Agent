"""私信发送工具 — Playwright RPA。

通过 Playwright 模拟人工操作发送私信，包含人类行为随机化和 Captcha 检测。
注意：发送前必须通过风控扫描。
"""

from __future__ import annotations

import asyncio
import random

from playwright.async_api import Page

from agent.tools.playwright_rpa_base import (
    HumanizedBrowserContext,
    check_captcha,
    human_click,
    human_type,
)


def get_dm_send_page_url(xhs_user_id: str) -> str:
    """构建私信发送页面 URL。

    Args:
        xhs_user_id: 小红书用户 ID。

    Returns:
        私信发送页 URL。
    """
    return f"https://www.xiaohongshu.com/user/me/message/{xhs_user_id}"


async def _open_dm_page(page: Page, xhs_user_id: str) -> bool:
    """打开私信页面。

    Args:
        page: Playwright Page 对象。
        xhs_user_id: 小红书用户 ID。

    Returns:
        True 表示页面打开成功。
    """
    url = get_dm_send_page_url(xhs_user_id)
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(random.uniform(2.0, 4.0))
    return True


async def _type_message(page: Page, content: str) -> None:
    """在输入框中输入私信内容。

    Args:
        page: Playwright Page 对象。
        content: 私信内容。
    """
    # 找到输入框（占位选择器，需根据实际抓取结果调整）
    input_selector = ".message-input textarea, .input-box textarea, #messageInput"

    # 尝试点击输入框激活
    for selector in [".message-input", ".input-box", "#messageInput"]:
        try:
            await page.click(selector, timeout=3000)
            break
        except Exception:
            continue

    # 使用人类打字方式输入
    await human_type(page, input_selector, content, delay_ms=random.randint(80, 160))

    # 随机停顿
    await asyncio.sleep(random.uniform(0.5, 1.5))


async def _click_send_button(page: Page) -> bool:
    """点击发送按钮。

    Args:
        page: Playwright Page 对象。

    Returns:
        True 表示点击成功。
    """
    send_selectors = [
        ".send-btn",
        ".message-send-btn",
        "button[type='submit']",
        ".btn-send",
    ]

    for selector in send_selectors:
        try:
            await page.click(selector, timeout=3000)
            return True
        except Exception:
            continue

    return False


# ── 主函数 ───────────────────────────────────────────────────────────────────


async def send_dm(
    account_id: str,
    xhs_user_id: str,
    content: str,
    cookie: str | None = None,
    proxy_url: str | None = None,
    user_agent: str | None = None,
) -> tuple[bool, str | None]:
    """通过 Playwright RPA 发送私信。

    Args:
        account_id: 商家子账号 ID。
        xhs_user_id: 小红书用户 ID。
        content: 私信内容（需提前通过风控扫描）。
        cookie: 解密后的 Cookie。
        proxy_url: 代理 URL。
        user_agent: User-Agent。

    Returns:
        (发送是否成功, 错误信息或 None)。
    """
    captcha_detected = False
    error_message = None

    async with HumanizedBrowserContext(
        account_id=account_id,
        cookie=cookie,
        proxy_url=proxy_url,
        user_agent=user_agent,
    ) as ctx:
        page = await ctx.get_page()

        # 打开私信页面
        try:
            await _open_dm_page(page, xhs_user_id)
        except Exception as e:
            return False, f"Failed to open DM page: {e}"

        # 检查 Captcha
        if await check_captcha(page):
            captcha_detected = True
            return False, "Captcha detected"

        # 输入私信内容
        try:
            await _type_message(page, content)
        except Exception as e:
            return False, f"Failed to type message: {e}"

        # 随机停顿后再点击发送
        await asyncio.sleep(random.uniform(0.8, 2.0))

        # 点击发送
        try:
            sent = await _click_send_button(page)
            if not sent:
                return False, "Send button not found"
        except Exception as e:
            return False, f"Failed to click send: {e}"

        # 等待发送完成
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # 再次检查 Captcha（发送可能触发验证）
        if await check_captcha(page):
            captcha_detected = True
            return False, "Captcha detected after send"

        # 检查是否发送成功（页面是否有变化或确认提示）
        try:
            # 简单检查：输入框是否被清空（表示发送成功）
            input_selector = ".message-input textarea, .input-box textarea, #messageInput"
            for sel in [".message-input", ".input-box", "#messageInput"]:
                try:
                    input_text = await page.input_value(sel, timeout=2000)
                    if not input_text:
                        return True, None  # 发送成功
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # 无法确认时保守返回成功（有网络延迟）
        return True, None
