import {
  Badge,
  ButtonLink,
  DataTable,
  ProgressBar,
  SectionCard,
  SectionHeader,
  StatCard,
  TimelineItem,
} from "@/components/DashboardUI";

const accountRows = [
  {
    账号: "小红书主号",
    平台: "小红书",
    状态: <Badge tone="success">在线</Badge>,
    "最近同步": "2 分钟前",
    操作: <ButtonLink href="/accounts">重新同步</ButtonLink>,
  },
  {
    账号: "种草副号",
    平台: "小红书",
    状态: <Badge tone="warning">授权即将过期</Badge>,
    "最近同步": "18 分钟前",
    操作: <ButtonLink href="/accounts">刷新授权</ButtonLink>,
  },
  {
    账号: "测试账号",
    平台: "小红书",
    状态: <Badge tone="danger">同步失败</Badge>,
    "最近同步": "1 小时前",
    操作: <ButtonLink href="/accounts">查看原因</ButtonLink>,
  },
];

const syncLogs = [
  {
    title: "资料同步成功",
    description: "昵称、头像和简介已完成同步。",
    time: "刚刚",
    tone: "success" as const,
  },
  {
    title: "Cookie 即将过期",
    description: "建议在 24 小时内重新授权，避免自动任务中断。",
    time: "15 分钟前",
    tone: "warning" as const,
  },
  {
    title: "代理连接正常",
    description: "当前账号的代理配置已验证通过。",
    time: "30 分钟前",
    tone: "accent" as const,
  },
];

export default function AccountsPage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="已连接账号" value="12" delta="+2 本周" tone="accent" />
          <StatCard label="在线账号" value="10" delta="稳定" tone="success" />
          <StatCard label="即将过期" value="2" delta="需处理" />
          <StatCard label="同步失败" value="1" delta="待修复" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <SectionCard>
            <SectionHeader
              title="扫码登录"
              description="为新账号拉起二维码，完成授权后自动进入资料同步流程。"
              action={<ButtonLink href="/accounts">刷新二维码</ButtonLink>}
            />
            <div className="space-y-4 p-5">
              <div className="rounded-3xl border border-border bg-bg-surface-dim p-6">
                <div className="mx-auto flex aspect-square max-w-[280px] items-center justify-center rounded-[28px] border border-border bg-bg-surface shadow-[0_12px_24px_rgba(255,107,138,0.06)]">
                  <div className="text-center">
                    <div className="mx-auto mb-3 h-16 w-16 rounded-2xl bg-accent/10" />
                    <p className="text-[14px] font-medium text-text-secondary">
                      二维码加载中
                    </p>
                    <p className="mt-1 text-[12px] text-text-muted">
                      请使用小红书 App 扫码
                    </p>
                  </div>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[12px] text-text-secondary">扫码状态</p>
                  <p className="mt-1 text-[18px] font-semibold text-text-primary">
                    等待扫码
                  </p>
                </div>
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[12px] text-text-secondary">Cookie 有效期</p>
                  <p className="mt-1 text-[18px] font-semibold text-text-primary">
                    19 小时
                  </p>
                </div>
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[12px] text-text-secondary">代理状态</p>
                  <p className="mt-1 text-[18px] font-semibold text-text-primary">
                    正常
                  </p>
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="账号列表"
              description="查看各账号的状态、同步时间和常用操作。"
              action={<ButtonLink href="/accounts" variant="secondary">添加账号</ButtonLink>}
            />
            <div className="p-5">
              <DataTable
                columns={[
                  { header: "账号", width: "32%" },
                  { header: "平台", width: "14%" },
                  { header: "状态", width: "18%" },
                  { header: "最近同步", width: "18%" },
                  { header: "操作", width: "18%" },
                ]}
                rows={accountRows}
              />
            </div>
          </SectionCard>
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <SectionCard>
            <SectionHeader
              title="Cookie 与授权"
              description="关注授权剩余时间，避免自动任务中断。"
            />
            <div className="space-y-5 p-5">
              <ProgressBar value={72} label="Cookie 剩余有效期" />
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[12px] text-text-secondary">授权方式</p>
                  <p className="mt-1 text-[16px] font-semibold text-text-primary">
                    扫码登录 + Cookie
                  </p>
                </div>
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[12px] text-text-secondary">代理配置</p>
                  <p className="mt-1 text-[16px] font-semibold text-text-primary">
                    已启用
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <ButtonLink href="/accounts">重新授权</ButtonLink>
                <ButtonLink href="/accounts" variant="secondary">
                  编辑代理
                </ButtonLink>
              </div>
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="最近同步记录"
              description="展示账号资料、Cookie 和代理配置的最新同步动态。"
            />
            <div className="space-y-3 p-5">
              {syncLogs.map((item) => (
                <TimelineItem key={item.title} {...item} />
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
