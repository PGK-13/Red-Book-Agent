import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "小红书营销自动化",
  description: "小红书商家营销自动化智能体平台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <Sidebar />
        <TopNav />
        <main className="lg:ml-[240px] mt-[64px] min-h-screen bg-bg-primary">
          {children}
        </main>
      </body>
    </html>
  );
}
