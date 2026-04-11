"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navItems } from "@/components/Sidebar";
import UserMenu from "@/components/UserMenu";

export default function TopNav() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 lg:left-[240px] right-0 h-[64px] bg-bg-surface border-b border-border z-30 flex items-center justify-between px-6">
      {/* 移动端 Logo */}
      <div className="lg:hidden flex items-center gap-2 shrink-0">
        <svg
          width="24"
          height="24"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M16 28s-10-6.5-10-14a6 6 0 0 1 10-4.47A6 6 0 0 1 26 14c0 7.5-10 14-10 14z"
            fill="#FF6B8A"
          />
        </svg>
        <span className="text-[16px] font-bold text-text-primary">
          RedFlow
        </span>
      </div>

      {/* 移动端导航（横向滚动） */}
      <nav className="lg:hidden flex items-center gap-1 overflow-x-auto mx-3">
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

      {/* 桌面端左侧留空 */}
      <div className="hidden lg:block" />

      {/* 右侧用户菜单 */}
      <div className="flex items-center gap-3 shrink-0">
        <UserMenu />
      </div>
    </header>
  );
}
