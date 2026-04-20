import {
  Badge,
  ButtonLink,
  SectionCard,
  SectionHeader,
  StatCard,
  TimelineItem,
} from "@/components/DashboardUI";

const threads = [
  {
    name: "用户 A",
    preview: "想问一下这套笔记模板可以直接复用吗？",
    time: "2 分钟前",
    state: "待回复",
  },
  {
    name: "用户 B",
    preview: "产品价格和发货时间可以再说明一下吗？",
    time: "12 分钟前",
    state: "人工接管",
  },
  {
    name: "用户 C",
    preview: "收到，谢谢，已经下单了。",
    time: "24 分钟前",
    state: "已完成",
  },
];

const quickReplies = [
  "谢谢你的留言，我们已经收到啦。",
  "可以的，我帮你补充一下详细说明。",
  "如果需要，我可以继续发你产品链接。",
];

const activity = [
  {
    title: "新会话已接入",
    description: "收到 4 条新评论，已进入待回复队列。",
    time: "刚刚",
    tone: "accent" as const,
  },
  {
    title: "人工接管中",
    description: "当前会话已由运营同学接管，系统暂停自动回复。",
    time: "8 分钟前",
    tone: "warning" as const,
  },
  {
    title: "回复已发送",
    description: "一条高频问题已通过快捷回复完成处理。",
    time: "30 分钟前",
    tone: "success" as const,
  },
];

export default function ConversationsPage() {
  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-[1440px] space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="待回复评论" value="14" delta="+3" tone="accent" />
          <StatCard label="待处理私信" value="9" delta="2 条超时" />
          <StatCard label="已接管会话" value="5" delta="人工处理中" tone="success" />
          <StatCard label="超时任务" value="2" delta="需关注" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]">
          <SectionCard>
            <SectionHeader
              title="会话列表"
              description="左侧按最新消息、风险状态和接管情况展示。"
            />
            <div className="space-y-3 p-5">
              {threads.map((item, index) => (
                <div
                  key={item.name}
                  className={`rounded-2xl border p-4 transition-colors ${
                    index === 0
                      ? "border-accent/30 bg-accent/5"
                      : "border-border bg-bg-surface"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-[14px] font-semibold text-text-primary">
                        {item.name}
                      </p>
                      <p className="text-[13px] leading-6 text-text-secondary">
                        {item.preview}
                      </p>
                    </div>
                    <Badge tone={index === 0 ? "accent" : index === 1 ? "warning" : "success"}>
                      {item.state}
                    </Badge>
                  </div>
                  <p className="mt-3 text-[12px] text-text-muted">{item.time}</p>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="消息线程"
              description="中间区域展示完整对话，右侧给出当前会话状态。"
              action={
                <div className="flex gap-2">
                  <ButtonLink href="/conversations">接管会话</ButtonLink>
                  <ButtonLink href="/conversations" variant="secondary">
                    释放会话
                  </ButtonLink>
                </div>
              }
            />
            <div className="grid gap-6 p-5 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-3 rounded-2xl bg-bg-surface-dim p-4">
                <div className="rounded-2xl bg-bg-surface p-4">
                  <p className="text-[13px] text-text-secondary">用户</p>
                  <p className="mt-1 text-[14px] text-text-primary">
                    这套模板可以直接复用吗？
                  </p>
                </div>
                <div className="ml-8 rounded-2xl bg-accent/10 p-4">
                  <p className="text-[13px] text-text-secondary">系统回复</p>
                  <p className="mt-1 text-[14px] text-text-primary">
                    可以，我们已经为你准备好可直接修改的内容草稿。
                  </p>
                </div>
                <div className="rounded-2xl bg-bg-surface p-4">
                  <p className="text-[13px] text-text-secondary">人工补充</p>
                  <p className="mt-1 text-[14px] text-text-primary">
                    如果需要，我可以继续帮你补充产品说明和链接。
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[13px] font-semibold text-text-primary">
                    当前会话状态
                  </p>
                  <p className="mt-1 text-[13px] leading-6 text-text-secondary">
                    在线 · 已开启人工接管 · 自动回复暂停
                  </p>
                </div>
                <div className="rounded-2xl bg-bg-surface-dim p-4">
                  <p className="text-[13px] font-semibold text-text-primary">
                    快捷回复
                  </p>
                  <div className="mt-3 space-y-2">
                    {quickReplies.map((reply) => (
                      <div
                        key={reply}
                        className="rounded-xl border border-border bg-bg-surface px-3 py-2 text-[13px] leading-6 text-text-secondary"
                      >
                        {reply}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>
        </div>

        <SectionCard>
          <SectionHeader
            title="最近互动动态"
            description="自动回复、人工接管和会话完成的最新记录。"
          />
          <div className="space-y-3 p-5">
            {activity.map((item) => (
              <TimelineItem key={item.title} {...item} />
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
