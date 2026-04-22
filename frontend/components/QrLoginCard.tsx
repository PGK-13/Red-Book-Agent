"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type UserInfo } from "@/lib/auth-context";
import { apiClient } from "@/lib/api-client";

type QrStatus = "loading" | "waiting" | "need_captcha" | "success" | "expired" | "error";

interface QrStartResponse {
  session_id: string;
  qr_image_base64: string;
}

interface QrPollResponse {
  status: "waiting" | "need_captcha" | "success" | "expired";
  token?: string;
  user?: UserInfo;
}

export default function QrLoginCard() {
  const router = useRouter();
  const { login } = useAuth();

  const [qrImage, setQrImage] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<QrStatus>("loading");
  const [captcha, setCaptcha] = useState("");
  const [captchaSubmitting, setCaptchaSubmitting] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const enterPreviewDashboard = useCallback(() => {
    const encodeBase64Url = (value: string) => {
      const bytes = new TextEncoder().encode(value);
      let binary = "";
      bytes.forEach((byte) => {
        binary += String.fromCharCode(byte);
      });
      return btoa(binary)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/g, "");
    };

    const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
    const payload = encodeBase64Url(
      JSON.stringify({
        nickname: "预览用户",
        avatar: null,
        xhs_user_id: "preview_user",
        exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24,
      })
    );
    const token = `${header}.${payload}.preview`;

    login(token, {
      nickname: "预览用户",
      avatar: null,
      xhs_user_id: "preview_user",
    });
    router.push("/dashboard");
  }, [login, router]);

  const fetchQrCode = useCallback(async () => {
    setStatus("loading");
    setQrImage(null);
    setSessionId(null);
    setCaptcha("");
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

  const submitCaptcha = useCallback(async () => {
    if (!sessionId || captcha.length !== 6 || captchaSubmitting) return;
    setCaptchaSubmitting(true);
    try {
      await apiClient.post("/api/v1/accounts/qr-login/submit-captcha", {
        session_id: sessionId,
        captcha,
      });
      setStatus("waiting");
    } catch {
      setStatus("error");
    } finally {
      setCaptchaSubmitting(false);
    }
  }, [sessionId, captcha, captchaSubmitting]);

  // Start polling when sessionId is set and status is waiting or need_captcha
  useEffect(() => {
    if (!sessionId || (status !== "waiting" && status !== "need_captcha")) return;

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
        } else if (data.status === "need_captcha") {
          setStatus("need_captcha");
        }
        // "waiting" → keep polling
      } catch {
        stopPolling();
        setStatus("error");
      }
    }, 1500);

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

        {status === "need_captcha" && (
          <div className="flex flex-col items-center justify-center gap-3 w-full px-4">
            <span className="text-text-secondary text-[14px] text-center">
              请输入六位验证码
            </span>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={captcha}
              onChange={(e) => setCaptcha(e.target.value.replace(/\D/g, ""))}
              onKeyDown={(e) => e.key === "Enter" && submitCaptcha()}
              placeholder="000000"
              className="w-full text-center text-[24px] tracking-[8px] border border-border rounded-lg h-[48px] outline-none focus:border-accent"
            />
            <button
              onClick={submitCaptcha}
              disabled={captcha.length !== 6 || captchaSubmitting}
              className="w-full bg-accent text-white font-semibold text-[14px] h-[40px] rounded-lg hover:brightness-110 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {captchaSubmitting ? "验证中..." : "确认"}
            </button>
          </div>
        )}

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
      <p className="text-text-secondary text-[14px]">
        {status === "need_captcha"
          ? "验证码已发送至小红书绑定的手机号"
          : "请使用小红书 App 扫码"}
      </p>

      {process.env.NODE_ENV !== "production" ? (
        <button
          type="button"
          onClick={enterPreviewDashboard}
          className="text-[13px] font-medium text-accent underline underline-offset-4"
        >
          先进入后台预览
        </button>
      ) : null}
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
