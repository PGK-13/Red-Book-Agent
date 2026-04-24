"""私信轮询工具 — Playwright RPA。

通过 Playwright 轮询商家端的私信消息列表，检测新增消息。
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from playwright.async_api import Page

from agent.tools.playwright_rpa_base import (
    HumanizedBrowserContext,
    check_captcha,
    human_scroll,
)

# ── 私信页面 URL ─────────────────────────────────────────────────────────────


def get_dm_page_url() -> str:
    """小红书私信页面 URL。"""
    return "https://www.xiaohongshu.com/message"


# ── 消息解析 ────────────────────────────────────────────────────────────────


async def parse_dm_conversations(page: Page) -> list[dict[str, Any]]:
    """解析私信会话列表。

    Args:
        page: Playwright Page 对象。

    Returns:
        会话列表，每项包含 xhs_user_id, last_message, unread_count。
    """
    conversations: list[dict[str, Any]] = []

    try:
        await page.wait_for_selector(".conversation-item", timeout=10000)
    except Exception:
        return conversations

    await human_scroll(page)

    conv_elements = await page.locator(".conversation-item").all()

    for el in conv_elements:
        try:
            user_id = await el.get_attribute("data-user-id") or ""
            last_msg_el = el.locator(".last-message").first
            last_message = await last_msg_el.inner_text() if await last_msg_el.count() > 0 else ""
            unread_el = el.locator(".unread-badge").first
            unread_count = 0
            if await unread_el.count() > 0:
                unread_text = await unread_el.inner_text()
                unread_count = int(unread_text) if unread_text.isdigit() else 0

            if user_id:
                conversations.append({
                    "xhs_user_id": user_id,
                    "last_message": last_message.strip(),
                    "unread_count": unread_count,
                })
        except Exception:
            continue

    return conversations


async def parse_dm_messages(page: Page) -> list[dict[str, Any]]:
    """解析当前私信会话的消息列表。

    Args:
        page: Playwright Page 对象。

    Returns:
        消息列表，每项包含 xhs_msg_id, role, content, sent_at。
    """
    messages: list[dict[str, Any]] = []

    try:
        await page.wait_for_selector(".message-item", timeout=10000)
    except Exception:
        return messages

    msg_elements = await page.locator(".message-item").all()

    for el in msg_elements:
        try:
            msg_id = await el.get_attribute("data-msg-id") or ""
            role = await el.get_attribute("data-role") or "user"  # user / assistant
            content_el = el.locator(".message-content").first
            content = await content_el.inner_text() if await content_el.count() > 0 else ""
            sent_at_el = el.locator(".message-time").first
            sent_at = await sent_at_el.inner_text() if await sent_at_el.count() > 0 else ""

            if msg_id and content:
                messages.append({
                    "xhs_msg_id": msg_id,
                    "role": role,
                    "content": content.strip(),
                    "sent_at": sent_at,
                })
        except Exception:
            continue

    return messages


# ── 主函数 ───────────────────────────────────────────────────────────────────


async def poll_dm_messages(
    account_id: str,
    cookie: str | None = None,
    proxy_url: str | None = None,
    user_agent: str | None = None,
    known_msg_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """轮询私信消息，返回新增消息。

    Args:
        account_id: 商家子账号 ID。
        cookie: 解密后的 Cookie。
        proxy_url: 代理 URL。
        user_agent: User-Agent。
        known_msg_ids: 已知的消息 ID 集合（用于去重）。

    Returns:
        (新增消息列表, 是否检测到 Captcha)。
    """
    captcha_detected = False
    known_msg_ids = known_msg_ids or set()

    async with HumanizedBrowserContext(
        account_id=account_id,
        cookie=cookie,
        proxy_url=proxy_url,
        user_agent=user_agent,
    ) as ctx:
        page = await ctx.get_page()

        url = get_dm_page_url()
        await page.goto(url, wait_until="networkidle")

        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)

        if await check_captcha(page):
            captcha_detected = True

        # 获取所有会话
        conversations = await parse_dm_conversations(page)

        new_messages: list[dict[str, Any]] = []

        # 遍历每个有未读消息的会话，获取详情
        for conv in conversations:
            if conv["unread_count"] == 0:
                continue

            xhs_user_id = conv["xhs_user_id"]

            # 点击进入会话
            try:
                conv_selector = f'.conversation-item[data-user-id="{xhs_user_id}"]'
                await page.click(conv_selector)
                await asyncio.sleep(random.uniform(1.0, 2.0))

                # 解析消息
                messages = await parse_dm_messages(page)

                # 去重
                for msg in messages:
                    if msg["xhs_msg_id"] not in known_msg_ids:
                        msg["xhs_user_id"] = xhs_user_id
                        new_messages.append(msg)

                # 返回会话列表
                await page.go_back()
                await asyncio.sleep(random.uniform(1.0, 2.0))

            except Exception:
                continue

    return new_messages, captcha_detected