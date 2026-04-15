"use client";

import { createContext, useContext } from "react";

export interface UserInfo {
  nickname: string;
  avatar: string | null;
  xhs_user_id: string;
}

export interface AuthState {
  token: string | null;
  user: UserInfo | null;
  isLoading: boolean;
}

export interface AuthContextValue extends AuthState {
  login(token: string, user: UserInfo): void;
  logout(): void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
