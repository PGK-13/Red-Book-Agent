"""端到端扫码登录测试脚本。

流程：打开小红书 → 截取二维码 → 等待扫码 → 检测登录成功 → 提取 Cookie
使用有头模式，确保 WebSocket 推送正常工作。
"""

import asyncio
import time
import sys

sys.path.insert(0, ".")

from playwright.async_api import async_playwright
from app.core.security import encrypt, decrypt


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # 有头模式
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # ── Step 1: 打开小红书 ──
        print("=" * 50)
        print("Step 1: 打开小红书...")
        await page.goto(
            "https://www.xiaohongshu.com",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        await page.wait_for_timeout(3000)
        print(f"  URL: {page.url}")

        # ── Step 2: 截取二维码 ──
        print("\nStep 2: 截取二维码...")
        qr_area = await page.query_selector(".code-area")
        if qr_area:
            await qr_area.screenshot(path="/tmp/xhs_qr_e2e.png")
            print("  ✓ 二维码已保存到 /tmp/xhs_qr_e2e.png")
        print("  请在弹出的浏览器窗口中用小红书 App 扫码！")
        print()

        # ── Step 3: 轮询等待登录成功 ──
        print("Step 3: 等待扫码登录（最多 5 分钟）...")
        start = time.time()
        timeout = 300
        logged_in = False

        while time.time() - start < timeout:
            elapsed = int(time.time() - start)

            # 检测方式 1: URL 跳转到 explore 页面（登录弹窗消失）
            login_modal = await page.query_selector(".login-modal")
            if not login_modal:
                # 弹窗消失了，等一下确认
                await page.wait_for_timeout(1000)
                login_modal_recheck = await page.query_selector(".login-modal")
                if not login_modal_recheck:
                    logged_in = True
                    break

            # 检测方式 2: 页面上出现用户头像
            avatar = await page.query_selector(".user-avatar, .reds-avatar")
            if avatar:
                logged_in = True
                break

            print(f"  [{elapsed}s] 等待中...", end="\r", flush=True)
            await page.wait_for_timeout(3000)

        if not logged_in:
            print("\n  ✗ 超时，未检测到登录成功")
            await browser.close()
            return

        elapsed_total = int(time.time() - start)
        print(f"\n  ✓ 登录成功！(耗时 {elapsed_total}s)")

        # ── Step 4: 提取 Cookie ──
        print("\nStep 4: 提取 Cookie...")
        cookies = await context.cookies()
        print(f"  共获取 {len(cookies)} 个 Cookie")

        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        print(f"  Cookie 字符串长度: {len(cookie_str)} chars")

        # 显示关键 Cookie（脱敏前 8 字符）
        key_names = {"a1", "web_session", "webId", "gid", "customer-sso-sid",
                     "access-token", "galaxy_creator_session_id", "xsecappid"}
        print("\n  关键 Cookie:")
        for c in cookies:
            if c["name"] in key_names or "session" in c["name"].lower() or "token" in c["name"].lower():
                masked = c["value"][:8] + "..." if len(c["value"]) > 8 else c["value"]
                print(f"    {c['name']}={masked} (domain={c.get('domain', '')})")

        # ── Step 5: 加密存储验证 ──
        print("\nStep 5: 加密存储验证...")
        encrypted = encrypt(cookie_str)
        decrypted = decrypt(encrypted)
        assert decrypted == cookie_str, "加密解密不一致！"
        print(f"  ✓ 加密后长度: {len(encrypted)} chars")
        print("  ✓ 解密验证通过，原始 Cookie 完整还原")

        # ── 结果 ──
        print("\n" + "=" * 50)
        print("端到端扫码登录流程全部通过 ✓")
        print(f"  Cookie 数量: {len(cookies)}")
        print(f"  Cookie 总长度: {len(cookie_str)} chars")
        print(f"  加密存储: OK")
        print(f"  耗时: {elapsed_total}s")
        print("=" * 50)

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
