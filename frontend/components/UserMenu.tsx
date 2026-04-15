"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const toggle = useCallback(() => setOpen((prev) => !prev), []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const initial = user?.nickname?.charAt(0) ?? "U";

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={toggle}
        className="flex items-center gap-2 cursor-pointer rounded-lg px-2 py-1 hover:bg-bg-surface-hover transition-colors"
        aria-haspopup="true"
        aria-expanded={open}
      >
        {user?.avatar ? (
          <img
            src={user.avatar}
            alt={user.nickname}
            className="w-[32px] h-[32px] rounded-full object-cover"
          />
        ) : (
          <span className="w-[32px] h-[32px] rounded-full bg-accent text-white flex items-center justify-center text-[14px] font-semibold">
            {initial}
          </span>
        )}
        <span className="text-[14px] text-text-primary font-medium hidden sm:inline">
          {user?.nickname ?? "用户"}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-[160px] bg-bg-surface border border-border rounded-lg shadow-lg py-1 z-50">
          <button
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="w-full text-left px-4 py-2 text-[14px] text-text-secondary hover:bg-bg-surface-hover hover:text-text-primary transition-colors cursor-pointer"
          >
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}
