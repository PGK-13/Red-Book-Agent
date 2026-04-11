"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import QrLoginCard from "@/components/QrLoginCard";

export default function LoginPage() {
  const { token, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && token) {
      router.push("/dashboard");
    }
  }, [isLoading, token, router]);

  if (isLoading || token) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#FFE0E6] via-[#FFF5F5] to-white flex items-center justify-center">
      <QrLoginCard />
    </div>
  );
}
