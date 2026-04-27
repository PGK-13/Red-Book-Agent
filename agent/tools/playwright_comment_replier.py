"""评论回复工具 — Playwright RPA。

通过 Playwright 模拟人工操作对笔记评论进行回复。
注意：发送前必须通过风控扫描。
回复字数限制：15~80 汉字。
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


def get_note_page_url(xhs_note_id: str) -> str:
    """构建笔记页面 URL。

    Args:
        xhs_note_id: 小红书笔记 ID。

    Returns:
        笔记页面 URL。
    """
    return f"https://www.xiaohongshu.com/explore/{xhs_note_id}"


async def _scroll_to_comment(page: Page, xhs_comment_id: str) -> bool:
    """滚动页面找到指定评论。

    Args:
        page: Playwright Page 对象。
        xhs_comment_id: 小红书评论 ID。

    Returns:
        True 表示找到评论。
    """
    # 占位选择器，需根据实际抓取结果调整
    comment_selector = f'.comment-item[data-comment-id="{xhs_comment_id}"]'

    for _ in range(5):  # 最多滚动 5 次
        try:
            if await page.is_visible(comment_selector, timeout=3000):
                return True
        except Exception:
            pass
        # 人类行为滚动
        await page.mouse.wheel(0, random.randint(300, 600))
        await asyncio.sleep(random.uniform(0.5, 1.2))

    return False


async def _click_reply_button(page: Page, xhs_comment_id: str) -> bool:
    """点击指定评论的回复按钮。

    Args:
        page: Playwright Page 对象。
        xhs_comment_id: 小红书评论 ID。

    Returns:
        True 表示点击成功。
    """
    reply_btn_selector = (
        f'.comment-item[data-comment-id="{xhs_comment_id}"] .reply-btn, '
        f'.comment-item[data-comment-id="{xhs_comment_id}"] .action-reply'
    )

    reply_selectors = [
        f'.comment-item[data-comment-id="{xhs_comment_id}"] .reply-btn',
        f'.comment-item[data-comment-id="{xhs_comment_id}"] .action-reply',
        f'.comment-item[data-comment-id="{xhs_comment_id}"] .comment-action:has-text("回复")',
    ]

    for selector in reply_selectors:
        try:
            await page.click(selector, timeout=3000)
            await asyncio.sleep(random.uniform(0.3, 0.8))
            return True
        except Exception:
            continue

    return False


async def _type_reply_content(page: Page, content: str) -> bool:
    """在回复输入框中输入回复内容。

    Args:
        page: Playwright Page 对象。
        content: 回复内容。

    Returns:
        True 表示输入成功。
    """
    # 回复输入框选择器（占位，需根据实际抓取结果调整）
    input_selectors = [
        ".reply-input textarea",
        ".comment-reply-input textarea",
        ".reply-box textarea",
        "#replyInput",
    ]

    for selector in input_selectors:
        try:
            await page.wait_for_selector(selector, timeout=3000)
            await human_type(page, selector, content, delay_ms=random.randint(60, 140))
            return True
        except Exception:
            continue

    return False


async def _click_submit_reply(page: Page) -> bool:
    """点击提交回复按钮。

    Args:
        page: Playwright Page 对象。

    Returns:
        True 表示点击成功。
    """
    submit_selectors = [
        ".reply-submit-btn",
        ".reply-box .submit-btn",
        ".btn-submit-reply",
        "button:has-text('发布')",
        "button:has-text('发送')",
    ]

    for selector in submit_selectors:
        try:
            await page.click(selector, timeout=3000)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            return True
        except Exception:
            continue

    return False


# ── 主函数 ───────────────────────────────────────────────────────────────────


async def send_comment_reply(
    account_id: str,
    xhs_note_id: str,
    xhs_comment_id: str,
    reply_content: str,
    cookie: str | None = None,
    proxy_url: str | None = None,
    user_agent: str | None = None,
) -> tuple[bool, str | None]:
    """通过 Playwright RPA 发送评论回复。

    Args:
        account_id: 商家子账号 ID。
        xhs_note_id: 小红书笔记 ID。
        xhs_comment_id: 小红书评论 ID。
        reply_content: 回复内容（需提前通过风控扫描，15~80 字）。
        cookie: 解密后的 Cookie。
        proxy_url: 代理 URL。
        user_agent: User-Agent。

    Returns:
        (发送是否成功, 错误信息或 None)。

    Raises:
        ValueError: 回复内容字数不在 15~80 范围内。
    """
    # 字数校验
    char_count = len(reply_content.strip())
    if char_count < 15 or char_count > 80:
        return False, f"Reply content must be 15-80 characters, got {char_count}"

    captcha_detected = False
    error_message = None

    async with HumanizedBrowserContext(
        account_id=account_id,
        cookie=cookie,
        proxy_url=proxy_url,
        user_agent=user_agent,
    ) as ctx:
        page = await ctx.get_page()

        # 打开笔记页面
        try:
            url = get_note_page_url(xhs_note_id)
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(random.uniform(2.0, 5.0))
        except Exception as e:
            return False, f"Failed to open note page: {e}"

        # 检查 Captcha
        if await check_captcha(page):
            return False, "Captcha detected"

        # 滚动到目标评论
        try:
            found = await _scroll_to_comment(page, xhs_comment_id)
            if not found:
                return False, f"Comment {xhs_comment_id} not found on page"
        except Exception as e:
            return False, f"Failed to scroll to comment: {e}"

        # 点击回复按钮
        try:
            clicked = await _click_reply_button(page, xhs_comment_id)
            if not clicked:
                return False, "Reply button not found"
        except Exception as e:
            return False, f"Failed to click reply button: {e}"

        # 输入回复内容
        try:
            typed = await _type_reply_content(page, reply_content)
            if not typed:
                return False, "Reply input box not found"
        except Exception as e:
            return False, f"Failed to type reply: {e}"

        # 随机停顿
        await asyncio.sleep(random.uniform(0.5, 1.5))

        # 点击提交
        try:
            submitted = await _click_submit_reply(page)
            if not submitted:
                return False, "Submit button not found"
        except Exception as e:
            return False, f"Failed to submit reply: {e}"

        # 等待提交完成
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # 再次检查 Captcha
        if await check_captcha(page):
            return False, "Captcha detected after submit"

    return True, None
