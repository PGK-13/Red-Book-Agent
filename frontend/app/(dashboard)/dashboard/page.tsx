import Link from "next/link";
import {
  Badge,
  ButtonLink,
  ModuleCard,
  SectionCard,
  SectionHeader,
  StatCard,
  TimelineItem,
} from "@/components/DashboardUI";

const moduleCards = [
  {
    title: "账号管理",
    description: "管理账号授权、扫码登录、Cookie 生命周期与资料同步。",
    status: "2 个待处理",
    actionLabel: "扫码登录",
    href: "/accounts",
    secondaryActionLabel: "同步资料",
    secondaryHref: "/accounts",
  },
  {
    title: "知识库",
    description: "导入文档、构建索引、维护检索权重和命中质量。",
    status: "1 个任务",
    actionLabel: "导入文档",
    href: "/knowledge",
    secondaryActionLabel: "开始索引",
    secondaryHref: "/knowledge",
  },
  {
    title: "内容管理",
    description: "创建草稿、生成文案、安排发布和审核流程。",
    status: "3 条草稿",
    actionLabel: "新建草稿",
    href: "/content",
    secondaryActionLabel: "生成内容",
    secondaryHref: "/content",
  },
  {
    title: "互动管理",
    description: "查看会话、处理评论、人工接管和快速回复。",
    status: "7 条待回复",
    actionLabel: "打开会话",
    href: "/conversations",
    secondaryActionLabel: "查看回复",
    secondaryHref: "/conversations",
  },
  {
    title: "风控管理",
    description: "执行敏感词扫描、频率限制和竞品过滤。",
    status: "1 条风险",
    actionLabel: "立即扫描",
    href: "/risk",
    secondaryActionLabel: "查看风险",
    secondaryHref: "/risk",
  },
  {
    title: "数据看板",
    description: "查看转化漏斗、账号趋势、发布效果和导出报表。",
    status: "今日更新",
    actionLabel: "查看报表",
    href: "/dashboard",
    secondaryActionLabel: "导出数据",
    secondaryHref: "/dashboard",
  },
];

const activities = [
  {
    title: "账号同步完成",
    description: "账号「小红书主号」资料已同步，昵称和头像已更新。",
    time: "2 分钟前",
    tone: "success" as const,
  },
  {
    title: "风控拦截一条内容",
    description: "生成草稿中检测到敏感词，已转入人工复核。",
    time: "18 分钟前",
    tone: "warning" as const,
  },
  {
    title: "内容草稿生成成功",
    description: "已生成 3 条文案建议，可继续编辑或提交审核。",
    time: "1 小时前",
    tone: "accent" as const,
  },
];

const metrics = [
  { label: "连接账号", value: "12", delta: "+2 本周", tone: "accent" as const },
  { label: "待处理草稿", value: "8", delta: "-3 今日", tone: "muted" as const },
  { label: "待回复会话", value: "24", delta: "3 条超时", tone: "muted" as const },
  { label: "风险拦截", value: "6", delta: "1 条升级", tone: "success" as const },
];

export default function DashboardPage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-6">
        <SectionCard className="overflow-hidden">
          <div className="grid gap-6 p-6 lg:grid-cols-[1.2fr_0.8fr] lg:p-8">
            <div className="space-y-5">
              <Badge tone="accent">欢迎回来</Badge>
              <div className="space-y-3">
                <h1 className="text-[30px] font-semibold tracking-tight text-text-primary lg:text-[38px]">
                  今天也一起把内容、互动和增长做好
                </h1>
                <p className="max-w-2xl text-[14px] leading-7 text-text-secondary">
                  RedFlow 把账号管理、知识库、内容生成、互动管理、风控和数据看板放在同一个工作台里，帮助你更稳定地跑通小红书运营流程。
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <ButtonLink href="/accounts">连接账号</ButtonLink>
                <ButtonLink href="/content" variant="secondary">
                  查看待办
                </ButtonLink>
                <ButtonLink href="/risk" variant="ghost">
                  立即扫描
                </ButtonLink>
              </div>
            </div>
            <div className="grid gap-3 rounded-2xl border border-border bg-bg-surface-dim p-4">
              <div className="rounded-2xl bg-bg-surface p-4 shadow-[0_10px_20px_rgba(255,107,138,0.06)]">
                <p className="text-[13px] text-text-secondary">今日状态</p>
                <p className="mt-2 text-[24px] font-semibold text-text-primary">
                  6 个模块正常运行
                </p>
                <p className="mt-1 text-[13px] leading-6 text-text-secondary">
                  账号同步、内容生成和风控扫描均已就绪。
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {[
                  ["待审核", "5"],
                  ["待发布", "3"],
                  ["告警", "2"],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-2xl bg-bg-surface px-4 py-3"
                  >
                    <p className="text-[12px] text-text-secondary">{label}</p>
                    <p className="mt-1 text-[22px] font-semibold text-text-primary">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </SectionCard>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <StatCard
              key={metric.label}
              label={metric.label}
              value={metric.value}
              delta={metric.delta}
              tone={metric.tone}
            />
          ))}
        </div>

        <SectionCard>
          <SectionHeader
            title="六个核心模块"
            description="从账号、知识到内容、互动、风控和数据，按模块组织你的后台流程。"
            action={<Link href="/accounts" className="text-[14px] font-medium text-accent">前往账号管理</Link>}
          />
          <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
            {moduleCards.map((card) => (
              <ModuleCard key={card.title} {...card} />
            ))}
          </div>
        </SectionCard>

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <SectionCard>
            <SectionHeader title="最近动态" description="查看同步、扫描、生成和审核的最新进度。" />
            <div className="space-y-3 p-5">
              {activities.map((item) => (
                <TimelineItem key={item.title} {...item} />
              ))}
            </div>
          </SectionCard>
          <SectionCard>
            <SectionHeader title="工作流状态" description="按模块监控当前流程是否正常。" />
            <div className="space-y-4 p-5">
              <div className="space-y-2 rounded-2xl bg-bg-surface-dim p-4">
                <div className="flex items-center justify-between">
                  <p className="text-[14px] font-semibold text-text-primary">
                    发布前风控
                  </p>
                  <Badge tone="success">已启用</Badge>
                </div>
                <p className="text-[13px] leading-6 text-text-secondary">
                  内容发布前必须经过敏感词与竞品过滤，确保不会直接出站。
                </p>
              </div>
              <div className="space-y-2 rounded-2xl bg-bg-surface-dim p-4">
                <div className="flex items-center justify-between">
                  <p className="text-[14px] font-semibold text-text-primary">
                    HITL 审核工作台
                  </p>
                  <Badge tone="accent">待处理 5 条</Badge>
                </div>
                <p className="text-[13px] leading-6 text-text-secondary">
                  适合人工复核内容、会话和风险事件，必要时可直接接管处理。
                </p>
              </div>
              <div className="space-y-2 rounded-2xl bg-bg-surface-dim p-4">
                <div className="flex items-center justify-between">
                  <p className="text-[14px] font-semibold text-text-primary">
                    数据导出
                  </p>
                  <Badge tone="neutral">可用</Badge>
                </div>
                <p className="text-[13px] leading-6 text-text-secondary">
                  支持导出报表和统计结果，方便做复盘和汇报。
                </p>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
