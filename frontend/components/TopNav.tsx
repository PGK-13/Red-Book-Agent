"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/dashboard", label: "数据看板" },
  { href: "/accounts", label: "账号管理" },
  { href: "/content", label: "内容管理" },
  { href: "/conversations", label: "实时会话" },
  { href: "/hitl", label: "HITL 审核" },
  { href: "/alerts", label: "告警中心" },
];

export default function TopNav() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 lg:left-[240px] right-0 h-[64px] bg-bg-surface border-b border-border z-30 flex items-center justify-between px-6">
      {/* 移动端 Logo */}
      <span className="lg:hidden text-[16px] font-bold text-text-primary">
        XHS Agent
      </span>

      {/* 移动端导航（横向滚动） */}
      <nav className="lg:hidden flex items-center gap-1 overflow-x-auto">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`shrink-0 px-3 h-[32px] flex items-center rounded-lg text-[13px] font-medium transition-colors ${
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* 右侧占位（后续放用户头像/通知） */}
      <div className="flex items-center gap-3">
        <div className="w-[32px] h-[32px] rounded-full bg-bg-surface-hover" />
      </div>
    </header>
  );
}
