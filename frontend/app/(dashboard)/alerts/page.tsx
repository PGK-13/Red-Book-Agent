import {
  Badge,
  ButtonLink,
  DataTable,
  SectionCard,
  SectionHeader,
  StatCard,
} from "@/components/DashboardUI";

const alertRows = [
  {
    告警名称: "同步失败",
    级别: <Badge tone="danger">高</Badge>,
    来源: "账号管理",
    状态: <Badge tone="warning">待处理</Badge>,
    操作: <ButtonLink href="/alerts">查看详情</ButtonLink>,
  },
  {
    告警名称: "风控命中上升",
    级别: <Badge tone="warning">中</Badge>,
    来源: "风控管理",
    状态: <Badge tone="accent">观察中</Badge>,
    操作: <ButtonLink href="/alerts">查看趋势</ButtonLink>,
  },
  {
    告警名称: "发布任务延迟",
    级别: <Badge tone="neutral">低</Badge>,
    来源: "内容管理",
    状态: <Badge tone="success">已处理</Badge>,
    操作: <ButtonLink href="/alerts">标记完成</ButtonLink>,
  },
];

export default function AlertsPage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="今日告警" value="8" delta="+2" tone="accent" />
          <StatCard label="高危告警" value="2" delta="需立即处理" />
          <StatCard label="已处理" value="5" delta="完成" tone="success" />
          <StatCard label="平均响应" value="6m" delta="较快" />
        </div>

        <SectionCard>
          <SectionHeader
            title="告警中心"
            description="统一管理同步失败、风控异常和发布延迟。"
            action={<ButtonLink href="/alerts" variant="secondary">全部标记已读</ButtonLink>}
          />
          <div className="p-5">
            <DataTable
              columns={[
                { header: "告警名称", width: "30%" },
                { header: "级别", width: "16%" },
                { header: "来源", width: "22%" },
                { header: "状态", width: "16%" },
                { header: "操作", width: "16%" },
              ]}
              rows={alertRows}
            />
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
