import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <Sidebar />
      <TopNav />
      <main className="lg:ml-[240px] mt-[64px] min-h-screen bg-bg-primary">
        {children}
      </main>
    </AuthGuard>
  );
}
