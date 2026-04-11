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
    label: "实时会话",
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
    href: "/hitl",
    label: "HITL 审核",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 2l2.5 5 5.5.8-4 3.9.9 5.3L10 14.5 5.1 17l.9-5.3-4-3.9 5.5-.8L10 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    href: "/alerts",
    label: "告警中心",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 2a1 1 0 01.993.883L11 3v.5c2.613.502 4.5 2.61 4.5 5.5v3l1.5 2H3l1.5-2v-3c0-2.89 1.887-4.998 4.5-5.5V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 16a2 2 0 104 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
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
      </nav>
    </aside>
  );
}
