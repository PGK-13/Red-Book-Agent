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

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex flex-col fixed left-0 top-0 h-full w-[240px] bg-bg-surface border-r border-border z-40">
      {/* Logo */}
      <div className="h-[64px] flex items-center px-6 border-b border-border">
        <span className="text-[18px] font-bold text-text-primary tracking-tight">
          XHS Agent
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 h-[40px] rounded-lg text-[14px] font-medium transition-colors ${
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-surface-hover"
              }`}
            >
              {isActive && (
                <span className="w-[3px] h-[20px] bg-accent rounded-full -ml-3 mr-0 absolute left-3" />
              )}
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
