import {
  Badge,
  ButtonLink,
  SectionCard,
  SectionHeader,
  StatCard,
  TimelineItem,
} from "@/components/DashboardUI";

const reviewQueue = [
  {
    title: "草稿：护肤种草文案",
    description: "命中低风险词，需要人工确认语气与引导方式。",
    time: "待审核",
    tone: "warning" as const,
  },
  {
    title: "评论：价格咨询",
    description: "可直接通过快捷回复处理，建议保留人工确认。",
    time: "排队中",
    tone: "accent" as const,
  },
  {
    title: "会话：售后跟进",
    description: "当前会话已升级给人工客服，等待处理结果。",
    time: "处理中",
    tone: "success" as const,
  },
];

export default function HitlPage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="待审核" value="5" delta="需要处理" tone="accent" />
          <StatCard label="批量审核" value="12" delta="今日" tone="success" />
          <StatCard label="已通过" value="38" delta="+8" />
          <StatCard label="已驳回" value="4" delta="需复看" />
        </div>

        <SectionCard>
          <SectionHeader
            title="HITL 审核工作台"
            description="适合人工复核草稿、会话和风险事件，必要时可直接接管。"
            action={
              <div className="flex flex-wrap gap-2">
                <ButtonLink href="/hitl">批量通过</ButtonLink>
                <ButtonLink href="/hitl" variant="secondary">
                  标记复核
                </ButtonLink>
              </div>
            }
          />
          <div className="grid gap-4 p-5 xl:grid-cols-[1.05fr_0.95fr]">
            <div className="space-y-3 rounded-2xl bg-bg-surface-dim p-4">
              <div className="rounded-2xl bg-bg-surface p-4">
                <p className="text-[13px] text-text-secondary">当前待审内容</p>
                <p className="mt-1 text-[15px] font-semibold text-text-primary">
                  这是一条待审核的内容草稿，系统已做初筛。
                </p>
              </div>
              <div className="rounded-2xl bg-bg-surface p-4">
                <p className="text-[13px] text-text-secondary">审查建议</p>
                <p className="mt-1 text-[14px] leading-7 text-text-primary">
                  建议保留开头引导语，避免过度营销词，并确认是否触发风控规则。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <ButtonLink href="/hitl">通过</ButtonLink>
                <ButtonLink href="/hitl" variant="secondary">
                  拒绝
                </ButtonLink>
                <ButtonLink href="/hitl" variant="ghost">
                  修改后通过
                </ButtonLink>
              </div>
            </div>

            <div className="space-y-3 rounded-2xl bg-bg-surface-dim p-4">
              <div className="flex items-center justify-between">
                <p className="text-[14px] font-semibold text-text-primary">
                  审核队列
                </p>
                <Badge tone="accent">5 条</Badge>
              </div>
              {reviewQueue.map((item) => (
                <TimelineItem key={item.title} {...item} />
              ))}
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
