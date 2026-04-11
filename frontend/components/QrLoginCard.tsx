"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type UserInfo } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";

type QrStatus = "loading" | "waiting" | "success" | "expired" | "error";

interface QrStartResponse {
  session_id: string;
  qr_image_base64: string;
}

interface QrPollResponse {
  status: "waiting" | "success" | "expired";
  token?: string;
  user?: UserInfo;
}

export default function QrLoginCard() {
  const router = useRouter();
  const { login } = useAuth();

  const [qrImage, setQrImage] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<QrStatus>("loading");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const fetchQrCode = useCallback(async () => {
    setStatus("loading");
    setQrImage(null);
    setSessionId(null);
    stopPolling();

    try {
      const data = await apiClient.post<QrStartResponse>(
        "/api/v1/accounts/qr-login/start",
        {}
      );
      setQrImage(data.qr_image_base64);
      setSessionId(data.session_id);
      setStatus("waiting");
    } catch {
      setStatus("error");
    }
  }, [stopPolling]);

  // Start polling when sessionId is set and status is waiting
  useEffect(() => {
    if (!sessionId || status !== "waiting") return;

    intervalRef.current = setInterval(async () => {
      try {
        const data = await apiClient.get<QrPollResponse>(
          `/api/v1/accounts/qr-login/status?session_id=${sessionId}`
        );

        if (data.status === "success" && data.token && data.user) {
          stopPolling();
          setStatus("success");
          login(data.token, data.user);
          router.push("/dashboard");
        } else if (data.status === "expired") {
          stopPolling();
          setStatus("expired");
        }
        // "waiting" → keep polling
      } catch {
        stopPolling();
        setStatus("error");
      }
    }, 3000);

    return () => stopPolling();
  }, [sessionId, status, login, router, stopPolling]);

  // Fetch QR code on mount
  useEffect(() => {
    fetchQrCode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8 w-[400px] flex flex-col items-center gap-6">
      {/* Brand Logo */}
      <div className="flex items-center gap-2">
        <svg
          width="32"
          height="32"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M16 28s-10-6.5-10-14a6 6 0 0 1 10-4.47A6 6 0 0 1 26 14c0 7.5-10 14-10 14z"
            fill="#FF6B8A"
          />
        </svg>
        <span className="text-[20px] font-semibold text-text-primary">
          RedFlow
        </span>
      </div>

      {/* Title */}
      <h1 className="text-[24px] font-semibold text-text-primary">扫码登录</h1>

      {/* QR Code Area */}
      <div className="relative w-[200px] h-[200px] rounded-xl overflow-hidden bg-bg-surface-dim flex items-center justify-center">
        {status === "loading" && <Spinner />}

        {status === "waiting" && qrImage && (
          <img
            src={`data:image/png;base64,${qrImage}`}
            alt="小红书扫码登录二维码"
            width={200}
            height={200}
            className="w-full h-full object-contain"
          />
        )}

        {status === "expired" && (
          <>
            {qrImage && (
              <img
                src={`data:image/png;base64,${qrImage}`}
                alt="已过期的二维码"
                width={200}
                height={200}
                className="w-full h-full object-contain opacity-30"
              />
            )}
            <div className="absolute inset-0 bg-white/70 flex flex-col items-center justify-center gap-3">
              <span className="text-text-secondary text-[14px]">二维码已过期</span>
              <button
                onClick={fetchQrCode}
                className="bg-accent text-white font-semibold text-[14px] px-5 h-[40px] rounded-lg hover:brightness-110 transition"
              >
                刷新二维码
              </button>
            </div>
          </>
        )}

        {status === "error" && (
          <div className="flex flex-col items-center justify-center gap-3">
            <span className="text-red-400 text-[14px]">加载失败</span>
            <button
              onClick={fetchQrCode}
              className="bg-accent text-white font-semibold text-[14px] px-5 h-[40px] rounded-lg hover:brightness-110 transition"
            >
              重试
            </button>
          </div>
        )}

        {status === "success" && (
          <div className="flex items-center justify-center">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true">
              <circle cx="24" cy="24" r="24" fill="#22C55E" opacity="0.15" />
              <path d="M15 24l6 6 12-12" stroke="#22C55E" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        )}
      </div>

      {/* Hint */}
      <p className="text-text-secondary text-[14px]">请使用小红书 App 扫码</p>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin w-8 h-8 text-accent"
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
  );
}
