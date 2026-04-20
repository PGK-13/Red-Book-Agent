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

const riskRows = [
  {
    规则名称: "敏感词检测",
    命中内容: "超低价、速来、私聊",
    严重级别: <Badge tone="danger">高</Badge>,
    处理状态: <Badge tone="warning">待复核</Badge>,
  },
  {
    规则名称: "竞品过滤",
    命中内容: "同类品牌比较文案",
    严重级别: <Badge tone="warning">中</Badge>,
    处理状态: <Badge tone="neutral">观察中</Badge>,
  },
  {
    规则名称: "频率限制",
    命中内容: "短时间内连续触发回复",
    严重级别: <Badge tone="accent">低</Badge>,
    处理状态: <Badge tone="success">已处理</Badge>,
  },
];

const riskLogs = [
  {
    title: "内容被拦截",
    description: "生成草稿命中敏感词，已自动阻断出站。",
    time: "刚刚",
    tone: "danger" as const,
  },
  {
    title: "规则更新完成",
    description: "敏感词库已加入 12 条新规则。",
    time: "10 分钟前",
    tone: "accent" as const,
  },
  {
    title: "风险扫描通过",
    description: "一条内容已通过风控，进入待发布队列。",
    time: "42 分钟前",
    tone: "success" as const,
  },
];

export default function RiskPage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="今日扫描数" value="58" delta="+12" tone="accent" />
          <StatCard label="拦截数" value="6" delta="风险上升" />
          <StatCard label="风险评分" value="82" delta="较高" tone="warning" />
          <StatCard label="通过率" value="89%" delta="+4%" tone="success" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[1fr_0.95fr]">
          <SectionCard>
            <SectionHeader
              title="内容扫描"
              description="在发布前先做敏感词、频率和竞品过滤。"
              action={<ButtonLink href="/risk">立即扫描</ButtonLink>}
            />
            <div className="space-y-4 p-5">
              <div className="min-h-[180px] rounded-3xl border border-dashed border-border bg-bg-surface-dim p-5">
                <p className="text-[13px] text-text-secondary">输入待扫描内容</p>
                <div className="mt-3 rounded-2xl bg-bg-surface p-4 text-[14px] leading-7 text-text-primary">
                  这是一条用于测试的内容样例，系统会在发布前自动识别敏感词、竞品信息和频率异常。
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <ButtonLink href="/risk">开始扫描</ButtonLink>
                <ButtonLink href="/risk" variant="secondary">
                  查看规则
                </ButtonLink>
              </div>
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="风险趋势"
              description="近 7 天拦截数和风险评分变化。"
            />
            <div className="space-y-5 p-5">
              <ProgressBar value={82} label="风险评分" />
              <div className="grid gap-3 sm:grid-cols-3">
                {[
                  ["近 7 天", "38 次"],
                  ["高风险内容", "6 条"],
                  ["人工复核", "4 条"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl bg-bg-surface-dim p-4">
                    <p className="text-[12px] text-text-secondary">{label}</p>
                    <p className="mt-1 text-[18px] font-semibold text-text-primary">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
              <div className="rounded-2xl bg-bg-surface-dim p-4">
                <p className="text-[13px] font-semibold text-text-primary">
                  处理策略
                </p>
                <p className="mt-1 text-[13px] leading-6 text-text-secondary">
                  所有出站内容必须先经过风控扫描，命中规则后可选择通过、拒绝或标记复核。
                </p>
              </div>
            </div>
          </SectionCard>
        </div>

        <SectionCard>
          <SectionHeader
            title="规则与命中"
            description="展示当前规则库、命中内容和处理状态。"
            action={<ButtonLink href="/risk" variant="secondary">编辑规则</ButtonLink>}
          />
          <div className="p-5">
            <DataTable
              columns={[
                { header: "规则名称", width: "24%" },
                { header: "命中内容", width: "36%" },
                { header: "严重级别", width: "18%" },
                { header: "处理状态", width: "22%" },
              ]}
              rows={riskRows}
            />
          </div>
        </SectionCard>

        <SectionCard>
          <SectionHeader
            title="最近风险日志"
            description="记录拦截、规则更新和通过的最新动态。"
          />
          <div className="space-y-3 p-5">
            {riskLogs.map((item) => (
              <TimelineItem key={item.title} {...item} />
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
