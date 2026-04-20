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

const documentRows = [
  {
    文件名: "爆款文案库.pdf",
    类型: "PDF",
    大小: "12.4 MB",
    状态: <Badge tone="success">已索引</Badge>,
    更新时间: "3 分钟前",
  },
  {
    文件名: "品牌卖点.xlsx",
    类型: "Excel",
    大小: "1.8 MB",
    状态: <Badge tone="warning">索引中</Badge>,
    更新时间: "12 分钟前",
  },
  {
    文件名: "竞品分析.docx",
    类型: "Word",
    大小: "4.1 MB",
    状态: <Badge tone="neutral">待处理</Badge>,
    更新时间: "1 小时前",
  },
];

const recentSearches = [
  {
    title: "搜索词：护肤种草文案",
    description: "命中 8 条高质量片段，已自动加权。",
    time: "2 分钟前",
    tone: "success" as const,
  },
  {
    title: "搜索词：夏季穿搭标题",
    description: "返回 12 条结果，其中 3 条被判定为爆款结构。",
    time: "18 分钟前",
    tone: "accent" as const,
  },
  {
    title: "搜索词：直播引流话术",
    description: "命中较少，建议补充更多文档后再次索引。",
    time: "1 小时前",
    tone: "warning" as const,
  },
];

export default function KnowledgePage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="文档总数" value="28" delta="+4 本周" tone="accent" />
          <StatCard label="已索引条目" value="2,640" delta="稳定" tone="success" />
          <StatCard label="待处理文件" value="3" delta="需上传" />
          <StatCard label="检索命中率" value="86%" delta="+5%" tone="success" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <SectionCard>
            <SectionHeader
              title="上传文档"
              description="拖拽或选择文件，系统会自动解析、分块并建立索引。"
              action={<ButtonLink href="/knowledge">上传文件</ButtonLink>}
            />
            <div className="space-y-4 p-5">
              <div className="rounded-3xl border border-dashed border-border bg-bg-surface-dim p-8 text-center">
                <div className="mx-auto mb-3 h-12 w-12 rounded-2xl bg-accent/10" />
                <p className="text-[15px] font-semibold text-text-primary">
                  拖拽文件到这里
                </p>
                <p className="mt-1 text-[13px] text-text-secondary">
                  支持 PDF、Word、Excel、Markdown
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[12px] text-text-secondary">混合检索</p>
                  <p className="mt-1 text-[16px] font-semibold text-text-primary">
                    已启用
                  </p>
                </div>
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[12px] text-text-secondary">向量权重</p>
                  <p className="mt-1 text-[16px] font-semibold text-text-primary">
                    0.65
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <ButtonLink href="/knowledge">开始索引</ButtonLink>
                <ButtonLink href="/knowledge" variant="secondary">
                  检索设置
                </ButtonLink>
              </div>
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="索引进度"
              description="查看当前处理中的知识库任务和索引质量。"
            />
            <div className="space-y-5 p-5">
              <ProgressBar value={74} label="当前索引任务进度" />
              <div className="grid gap-3 sm:grid-cols-3">
                {[
                  ["高质量命中", "1,024"],
                  ["平均召回", "0.83"],
                  ["更新时间", "今日"],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-2xl bg-bg-surface-dim p-4"
                  >
                    <p className="text-[12px] text-text-secondary">{label}</p>
                    <p className="mt-1 text-[18px] font-semibold text-text-primary">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
              <div className="rounded-2xl bg-bg-surface-dim p-4">
                <p className="text-[13px] font-semibold text-text-primary">
                  检索规则
                </p>
                <p className="mt-1 text-[13px] leading-6 text-text-secondary">
                  采用向量 + 关键词混合检索，优先命中高权重内容，避免过于泛化的结果。
                </p>
              </div>
            </div>
          </SectionCard>
        </div>

        <SectionCard>
          <SectionHeader
            title="文档列表"
            description="管理已上传文件、处理状态和最近更新时间。"
            action={<ButtonLink href="/knowledge" variant="secondary">重新索引</ButtonLink>}
          />
          <div className="p-5">
            <DataTable
              columns={[
                { header: "文件名", width: "34%" },
                { header: "类型", width: "12%" },
                { header: "大小", width: "12%" },
                { header: "状态", width: "20%" },
                { header: "更新时间", width: "12%" },
              ]}
              rows={documentRows}
            />
          </div>
        </SectionCard>

        <SectionCard>
          <SectionHeader
            title="最近查询"
            description="展示知识库搜索词、命中数量和建议调整方向。"
          />
          <div className="space-y-3 p-5">
            {recentSearches.map((item) => (
              <TimelineItem key={item.title} {...item} />
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
