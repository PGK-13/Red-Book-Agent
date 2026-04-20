"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthContext, type UserInfo } from "@/lib/auth-context";

const TOKEN_KEY = "token";

function parseJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    if (!base64) return null;
    const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function extractUser(payload: Record<string, unknown>): UserInfo {
  return {
    nickname: (payload.nickname as string) ?? "",
    avatar: (payload.avatar as string) ?? null,
    xhs_user_id: (payload.xhs_user_id as string) ?? "",
  };
}

function isExpired(payload: Record<string, unknown>): boolean {
  const exp = payload.exp as number | undefined;
  if (!exp) return false;
  return Date.now() >= exp * 1000;
}

export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  const login = useCallback((jwt: string, userInfo: UserInfo) => {
    localStorage.setItem(TOKEN_KEY, jwt);
    setToken(jwt);
    setUser(userInfo);
  }, []);

  // On mount: read JWT from localStorage, validate expiry
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const stored = localStorage.getItem(TOKEN_KEY);
      if (stored) {
        const payload = parseJwtPayload(stored);
        if (payload && !isExpired(payload)) {
          setToken(stored);
          setUser(extractUser(payload));
        } else {
          localStorage.removeItem(TOKEN_KEY);
        }
      }
      setIsLoading(false);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, []);

  const value = useMemo(
    () => ({ token, user, isLoading, login, logout }),
    [token, user, isLoading, login, logout]
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}
