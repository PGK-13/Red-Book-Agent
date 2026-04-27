"""评论监测工具 — Playwright RPA。

通过 Playwright 轮询指定笔记的新增评论，支持增量检测。
1. 点击"按时间排序"确保评论列表时间序稳定
2. 解析评论时间戳，过滤出晚于 last_checked_at 的新评论
3. Redis xhs_comment_id 集合做幂等兜底，避免重复处理
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from playwright.async_api import Page

from agent.tools.playwright_rpa_base import (
    HumanizedBrowserContext,
    check_captcha,
    human_click,
    human_scroll,
)

# ── 常量 ─────────────────────────────────────────────────────────────────────

# 按时间排序按钮的选择器（优先匹配文本，再匹配固定 class）
_TIME_SORT_SELECTORS = [
    "text=按时间排序",
    "text=最新",
    ".sort-tab:last-child",
    ".sort-item:last-child",
    "[data-sort='time']",
    "[data-sort='latest']",
]

# 评论时间戳选择器列表
_TIME_SELECTORS = [
    ".comment-time",
    ".comment-item .time",
    ".comment-date",
    "time",
]


def _parse_relative_time(text: str, now: datetime | None = None) -> datetime | None:
    """将小红书相对时间文本解析为绝对时间。

    支持格式：
    - "刚刚"
    - "X分钟前"
    - "X小时前"
    - "X天前"
    - "X月X日 HH:mm"
    - "YYYY-MM-DD"

    Args:
        text: 时间文本。
        now: 当前时间基准（默认 UTC now）。

    Returns:
        绝对时间，解析失败返回 None。
    """
    if not text:
        return None

    text = text.strip()
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        if "刚刚" in text:
            return now
        elif "分钟前" in text:
            minutes = int("".join(c for c in text if c.isdigit()) or "1")
            return now - timedelta(minutes=minutes)
        elif "小时前" in text:
            hours = int("".join(c for c in text if c.isdigit()) or "1")
            return now - timedelta(hours=hours)
        elif "天前" in text:
            days = int("".join(c for c in text if c.isdigit()) or "1")
            return now - timedelta(days=days)
        elif "昨天" in text:
            # "昨天 HH:mm"
            time_part = text.replace("昨天", "").strip()
            h, m = time_part.split(":") if ":" in time_part else ("0", "0")
            result = now - timedelta(days=1)
            return result.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        elif "-" in text and ":" in text:
            # "MM-DD HH:mm" or "YYYY-MM-DD HH:mm"
            return datetime.strptime(text, "%m-%d %H:%M").replace(
                year=now.year, tzinfo=timezone.utc
            )
        elif ":" in text:
            # "HH:mm" (今天)
            h, m = text.split(":")
            return now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except (ValueError, IndexError):
        pass

    return None


# ── 笔记评论页面 URL ─────────────────────────────────────────────────────────


def get_note_comments_url(xhs_note_id: str) -> str:
    """构建笔记评论页 URL。

    Args:
        xhs_note_id: 小红书笔记 ID。

    Returns:
        笔记评论页 URL。
    """
    return f"https://www.xiaohongshu.com/explore/{xhs_note_id}"


# ── 排序按钮点击 ─────────────────────────────────────────────────────────────


async def sort_comments_by_time(page: Page) -> bool:
    """点击"按时间排序"按钮，确保评论列表按时间倒序排列。

    Args:
        page: Playwright Page 对象。

    Returns:
        True 表示点击成功。
    """
    for selector in _TIME_SORT_SELECTORS:
        try:
            if await page.is_visible(selector, timeout=2000):
                await human_click(page, selector)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                return True
        except Exception:
            continue
    return False


# ── 评论数据解析 ─────────────────────────────────────────────────────────────


async def parse_comment_items(
    page: Page,
    last_checked_at: datetime | None = None,
    stop_on_seen: bool = True,
) -> list[dict[str, Any]]:
    """解析页面上的评论列表。

    按时间倒序排列（需先调用 sort_comments_by_time）。

    Args:
        page: Playwright Page 对象。
        last_checked_at: 上次轮询时间。只返回此时间之后的新评论。
        stop_on_seen: 遇到已知评论时是否停止滚动。

    Returns:
        评论数据列表，每项包含 xhs_comment_id, xhs_user_id, content, image_urls, parsed_at。
    """
    comments: list[dict[str, Any]] = []

    # 等待评论列表加载
    try:
        await page.wait_for_selector(".comment-item", timeout=10000)
    except Exception:
        return comments

    # 滚动加载更多评论（人类行为）
    await human_scroll(page)
    await asyncio.sleep(random.uniform(0.5, 1.0))

    # 获取所有评论元素
    comment_elements = await page.locator(".comment-item").all()

    for element in comment_elements:
        try:
            comment_id = await element.get_attribute("data-comment-id") or ""

            # 评论内容
            content_el = element.locator(".comment-content").first
            content = await content_el.inner_text() if await content_el.count() > 0 else ""

            # 用户 ID
            user_id_el = element.locator("[data-user-id]").first
            user_id = ""
            try:
                user_id = await user_id_el.get_attribute("data-user-id") or ""
            except Exception:
                pass

            # 评论时间戳
            parsed_at: datetime | None = None
            for time_sel in _TIME_SELECTORS:
                try:
                    time_el = element.locator(time_sel).first
                    if await time_el.count() > 0:
                        time_text = await time_el.inner_text()
                        parsed = _parse_relative_time(time_text)
                        if parsed is not None:
                            parsed_at = parsed
                            break
                except Exception:
                    continue

            # 图片
            image_urls: list[str] = []
            try:
                image_els = element.locator(".comment-images img")
                for img_el in await image_els.all():
                    src = await img_el.get_attribute("src")
                    if src:
                        image_urls.append(src)
            except Exception:
                pass

            if comment_id and content:
                # 时间过滤：只保留 last_checked_at 之后的新评论
                if last_checked_at is not None and parsed_at is not None:
                    if parsed_at <= last_checked_at:
                        # 已到时间边界，之后的评论都更旧（时间倒序），停止收集
                        break

                comments.append({
                    "xhs_comment_id": comment_id,
                    "xhs_user_id": user_id,
                    "content": content.strip(),
                    "image_urls": image_urls,
                    "parsed_at": parsed_at,
                })
        except Exception:
            continue

    return comments


# ── 主函数 ───────────────────────────────────────────────────────────────────


async def poll_note_comments(
    account_id: str,
    xhs_note_id: str,
    last_checked_at: datetime | None,
    known_comment_ids: set[str] | None = None,
    cookie: str | None = None,
    proxy_url: str | None = None,
    user_agent: str | None = None,
) -> tuple[list[dict[str, Any]], datetime, bool]:
    """轮询指定笔记的评论列表，返回新增评论（时间增量 + ID 去重）。

    流程：
    1. 点击"按时间排序"确保列表按时间倒序
    2. 解析所有可见评论及其时间戳
    3. 过滤：只保留 parsed_at > last_checked_at 的评论
    4. 去重：排除 known_comment_ids 中已有的评论 ID

    Args:
        account_id: 商家子账号 ID。
        xhs_note_id: 小红书笔记 ID。
        last_checked_at: 上次轮询时间。首次调用传 None，返回全部可见评论。
        known_comment_ids: 已知评论 ID 集合（Redis 幂等兜底）。
        cookie: 解密后的 Cookie。
        proxy_url: 代理 URL。
        user_agent: User-Agent。

    Returns:
        (新增评论列表, 本次轮询时间, 是否检测到 Captcha)。
    """
    captcha_detected = False
    poll_time = datetime.now(timezone.utc)

    async with HumanizedBrowserContext(
        account_id=account_id,
        cookie=cookie,
        proxy_url=proxy_url,
        user_agent=user_agent,
    ) as ctx:
        page = await ctx.get_page()

        url = get_note_comments_url(xhs_note_id)
        await page.goto(url, wait_until="networkidle")

        # 注入随机延迟
        await asyncio.sleep(random.uniform(2.0, 5.0))

        # 检查 Captcha
        if await check_captcha(page):
            captcha_detected = True

        # 点击"按时间排序"
        await sort_comments_by_time(page)

        # 再次短暂等待排序生效
        await asyncio.sleep(random.uniform(0.5, 1.5))

        # 检查 Captcha
        if not captcha_detected and await check_captcha(page):
            captcha_detected = True

        # 解析评论（时间过滤）
        all_comments = await parse_comment_items(
            page,
            last_checked_at=last_checked_at,
        )

        # ID 去重（Redis 幂等兜底）
        known_ids = known_comment_ids or set()
        new_comments = [
            c for c in all_comments if c["xhs_comment_id"] not in known_ids
        ]

        return new_comments, poll_time, captcha_detected


class CaptchaDetectedError(Exception):
    """Captcha 检测异常。"""
    pass