"use client";

import { usePathname } from "next/navigation";
import UserMenu from "@/components/UserMenu";

const titleMap: Record<string, string> = {
  "/dashboard": "数据看板",
  "/accounts": "账号管理",
  "/knowledge": "知识库",
  "/content": "内容管理",
  "/conversations": "互动管理",
  "/risk": "风控管理",
  "/hitl": "审核工作台",
  "/alerts": "告警中心",
};

export default function TopNav() {
  const pathname = usePathname();
  const matchedPath = Object.keys(titleMap).find((path) =>
    pathname.startsWith(path)
  );
  const title = matchedPath ? titleMap[matchedPath] : "RedFlow";

  return (
    <header className="fixed top-0 left-0 lg:left-[240px] right-0 h-[64px] bg-bg-surface/90 backdrop-blur-md border-b border-border z-30 flex items-center justify-between px-6">
      <div className="flex min-w-0 items-center gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-[18px] font-semibold tracking-tight text-text-primary">
            {title}
          </h1>
          <p className="hidden text-[12px] text-text-secondary sm:block">
            中文浅粉后台，围绕账号、内容、互动、风控与数据协同
          </p>
        </div>
      </div>

      <div className="hidden min-w-0 flex-1 items-center justify-center px-8 lg:flex">
        <label className="flex h-[40px] w-full max-w-[420px] items-center gap-2 rounded-full border border-border bg-bg-surface-dim px-4 text-[14px] text-text-muted">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M12.5 12.5L16 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span>搜索账号、内容、任务或告警</span>
        </label>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <button
          type="button"
          className="hidden h-[40px] rounded-full border border-border bg-bg-surface px-4 text-[14px] font-medium text-text-primary transition-colors hover:bg-bg-surface-hover sm:inline-flex"
        >
          新建任务
        </button>
        <button
          type="button"
          className="relative inline-flex h-[40px] w-[40px] items-center justify-center rounded-full border border-border bg-bg-surface text-text-secondary transition-colors hover:bg-bg-surface-hover"
          aria-label="通知"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M10 2a1 1 0 01.993.883L11 3v.5c2.613.502 4.5 2.61 4.5 5.5v3l1.5 2H3l1.5-2v-3c0-2.89 1.887-4.998 4.5-5.5V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5" />
            <path d="M8 16a2 2 0 104 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-accent" />
        </button>
        <UserMenu />
      </div>
    </header>
  );
}
