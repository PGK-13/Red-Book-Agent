import {
  Badge,
  ButtonLink,
  DataTable,
  SectionCard,
  SectionHeader,
  StatCard,
  TimelineItem,
} from "@/components/DashboardUI";

const draftRows = [
  {
    标题: "夏季护肤种草文案",
    账号: "小红书主号",
    状态: <Badge tone="warning">待审核</Badge>,
    更新时间: "5 分钟前",
    操作: <ButtonLink href="/content">编辑草稿</ButtonLink>,
  },
  {
    标题: "穿搭标题优化",
    账号: "种草副号",
    状态: <Badge tone="success">已通过</Badge>,
    更新时间: "20 分钟前",
    操作: <ButtonLink href="/content">查看详情</ButtonLink>,
  },
  {
    标题: "直播开场话术",
    账号: "测试账号",
    状态: <Badge tone="danger">风控拦截</Badge>,
    更新时间: "1 小时前",
    操作: <ButtonLink href="/risk">查看原因</ButtonLink>,
  },
];

const generatedLogs = [
  {
    title: "内容生成完成",
    description: "已基于知识库生成 3 条草稿，等待人工复核。",
    time: "刚刚",
    tone: "success" as const,
  },
  {
    title: "发布计划更新",
    description: "今晚 20:00 的发布任务已重新排期。",
    time: "18 分钟前",
    tone: "accent" as const,
  },
  {
    title: "风险扫描未通过",
    description: "一条标题命中敏感词，已退回修改。",
    time: "42 分钟前",
    tone: "warning" as const,
  },
];

export default function ContentPage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="草稿总数" value="18" delta="+4" tone="accent" />
          <StatCard label="待审核" value="5" delta="需处理" />
          <StatCard label="已发布" value="9" delta="稳定" tone="success" />
          <StatCard label="计划发布" value="4" delta="今晚" tone="muted" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <SectionCard>
            <SectionHeader
              title="新建草稿"
              description="先选账号，再生成内容，最后进入风控与发布流程。"
              action={<ButtonLink href="/content">生成内容</ButtonLink>}
            />
            <div className="space-y-4 p-5">
              <div className="rounded-2xl bg-bg-surface-dim p-4">
                <p className="text-[12px] text-text-secondary">目标账号</p>
                <p className="mt-1 text-[16px] font-semibold text-text-primary">
                  小红书主号
                </p>
              </div>
              <div className="rounded-2xl bg-bg-surface-dim p-4">
                <p className="text-[12px] text-text-secondary">内容类型</p>
                <p className="mt-1 text-[16px] font-semibold text-text-primary">
                  种草笔记 / 标题优化 / 直播话术
                </p>
              </div>
              <div className="rounded-2xl bg-bg-surface-dim p-4">
                <p className="text-[12px] text-text-secondary">风控状态</p>
                <p className="mt-1 text-[16px] font-semibold text-text-primary">
                  待扫描
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <ButtonLink href="/content">新建草稿</ButtonLink>
                <ButtonLink href="/risk" variant="secondary">
                  预检内容
                </ButtonLink>
              </div>
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="发布计划"
              description="查看今天、明天和本周的内容排期。"
            />
            <div className="space-y-3 p-5">
              {[
                ["今天 20:00", "穿搭种草笔记", "待发布"],
                ["明天 11:30", "品牌卖点图文", "已排期"],
                ["本周五 18:00", "直播预热笔记", "待确认"],
              ].map(([time, title, status]) => (
                <div
                  key={time}
                  className="flex items-center justify-between rounded-2xl bg-bg-surface-dim p-4"
                >
                  <div>
                    <p className="text-[13px] text-text-secondary">{time}</p>
                    <p className="mt-1 text-[15px] font-semibold text-text-primary">
                      {title}
                    </p>
                  </div>
                  <Badge tone="accent">{status}</Badge>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>

        <SectionCard>
          <SectionHeader
            title="草稿列表"
            description="集中查看生成结果、审核状态和后续动作。"
            action={<ButtonLink href="/content" variant="secondary">查看模板库</ButtonLink>}
          />
          <div className="p-5">
            <DataTable
              columns={[
                { header: "标题", width: "34%" },
                { header: "账号", width: "18%" },
                { header: "状态", width: "18%" },
                { header: "更新时间", width: "16%" },
                { header: "操作", width: "14%" },
              ]}
              rows={draftRows}
            />
          </div>
        </SectionCard>

        <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
          <SectionCard>
            <SectionHeader
              title="模板库"
              description="快速调用标题模板、封面模板和爆款结构。"
            />
            <div className="grid gap-3 p-5 sm:grid-cols-3">
              {["标题模板", "封面模板", "爆款结构模板"].map((item) => (
                <div key={item} className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[14px] font-semibold text-text-primary">{item}</p>
                  <p className="mt-1 text-[13px] leading-6 text-text-secondary">
                    可直接复用，也可在生成时微调语气和长度。
                  </p>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="最近生成记录"
              description="记录内容生成、审核通过与风控拦截情况。"
            />
            <div className="space-y-3 p-5">
              {generatedLogs.map((item) => (
                <TimelineItem key={item.title} {...item} />
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
