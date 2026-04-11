"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !token) {
      router.push("/login");
    }
  }, [isLoading, token, router]);

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-bg-primary flex items-center justify-center">
        <svg
          className="animate-spin w-10 h-10 text-accent"
          viewBox="0 0 24 24"
          fill="none"
          aria-label="加载中"
        >
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="3"
            strokeDasharray="50"
            strokeLinecap="round"
            className="opacity-25"
          />
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="3"
            strokeDasharray="50"
            strokeDashoffset="35"
            strokeLinecap="round"
          />
        </svg>
      </div>
    );
  }

  if (!token) {
    return null;
  }

  return <>{children}</>;
}
