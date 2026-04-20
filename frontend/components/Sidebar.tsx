"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const navItems = [
  {
    href: "/dashboard",
    label: "数据看板",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <rect x="2" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    href: "/accounts",
    label: "账号管理",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <circle cx="10" cy="7" r="3.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M3 17.5c0-3.5 3.134-5.5 7-5.5s7 2 7 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/knowledge",
    label: "知识库",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M5 3.5h9a2 2 0 012 2v9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M4 5.5A2.5 2.5 0 016.5 3h8A1.5 1.5 0 0116 4.5v11A1.5 1.5 0 0114.5 17h-8A2.5 2.5 0 014 14.5v-9z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M7 7.5h5M7 10h5M7 12.5h3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/content",
    label: "内容管理",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M4 3h12a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V4a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M6 7h8M6 10h8M6 13h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/conversations",
    label: "互动管理",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v9a1 1 0 01-1 1h-4l-3 3v-3H4a1 1 0 01-1-1V4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx="7" cy="8.5" r="1" fill="currentColor" />
        <circle cx="10" cy="8.5" r="1" fill="currentColor" />
        <circle cx="13" cy="8.5" r="1" fill="currentColor" />
      </svg>
    ),
  },
  {
    href: "/risk",
    label: "风控管理",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 2l6 2v5c0 4.2-2.4 7.5-6 9-3.6-1.5-6-4.8-6-9V4l6-2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M8 10l1.8 1.8L12.5 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

const utilityItems = [
  {
    href: "/hitl",
    label: "审核工作台",
  },
  {
    href: "/alerts",
    label: "告警中心",
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex flex-col fixed left-0 top-0 h-full w-[240px] bg-bg-surface border-r border-border z-40">
      {/* Logo */}
      <div className="h-[64px] flex items-center gap-2 px-6 border-b border-border shrink-0">
        <svg
          width="28"
          height="28"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M16 28s-10-6.5-10-14a6 6 0 0 1 10-4.47A6 6 0 0 1 26 14c0 7.5-10 14-10 14z"
            fill="#FF6B8A"
          />
        </svg>
        <span className="text-[18px] font-bold text-text-primary tracking-tight">
          RedFlow
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
              className={`relative flex items-center gap-3 px-3 h-[40px] rounded-lg text-[14px] font-medium transition-colors ${
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-surface-hover"
              }`}
            >
              {isActive && (
                <span className="absolute left-0 top-[10px] w-[3px] h-[20px] bg-accent rounded-full" />
              )}
              {item.icon}
              {item.label}
            </Link>
          );
        })}
        <div className="mt-4 px-3">
          <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            其他页面
          </p>
          <div className="space-y-1">
            {utilityItems.map((item) => {
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-lg px-3 h-[36px] text-[13px] font-medium transition-colors ${
                    isActive
                      ? "bg-accent/10 text-accent"
                      : "text-text-secondary hover:text-text-primary hover:bg-bg-surface-hover"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>
    </aside>
  );
}
