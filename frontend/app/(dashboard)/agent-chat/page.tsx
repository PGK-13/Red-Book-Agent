"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { SectionCard } from "@/components/DashboardUI";

// ── Types ──

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  ragSources?: RagSource[];
  model?: string;
}

interface RagSource {
  content: string;
  score: number;
  source_doc_id: string | null;
}

interface ChatResponse {
  reply: string;
  rag_sources: RagSource[];
  conversation_id: string;
  model: string;
}

interface ModelInfo {
  id: string;
  name: string;
  available: boolean;
}

// ── Helpers ──

function generateId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).substring(2, 15);
}

function getOrCreateConversationId(): string {
  if (typeof window === "undefined") return generateId();
  const stored = localStorage.getItem("agent_conversation_id");
  if (stored) return stored;
  const id = generateId();
  localStorage.setItem("agent_conversation_id", id);
  return id;
}

// ── Component ──

export default function AgentChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(getOrCreateConversationId);
  const [selectedModel, setSelectedModel] = useState("MiniMax-M2.7");
  const [models, setModels] = useState<ModelInfo[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 加载可用模型列表
  useEffect(() => {
    apiClient
      .get<{ models: ModelInfo[] }>("/api/v1/agent/models")
      .then((data) => {
        setModels(data.models);
        // 默认选第一个可用的
        const firstAvailable = data.models.find((m) => m.available);
        if (firstAvailable) setSelectedModel(firstAvailable.id);
      })
      .catch(() => {
        setModels([
          { id: "MiniMax-M2.7", name: "MiniMax", available: false },
          { id: "deepseek-chat", name: "DeepSeek", available: false },
          { id: "gpt-4o", name: "GPT-4o", available: false },
        ]);
      });
  }, []);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMessage: Message = {
      id: generateId(),
      role: "user",
      content: trimmed,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const data = await apiClient.post<ChatResponse>("/api/v1/agent/chat", {
        message: trimmed,
        conversation_id: conversationId,
        model: selectedModel,
      });

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: data.reply,
          ragSources: data.rag_sources,
          model: data.model,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content:
            "抱歉，请求失败：" +
            (error instanceof Error ? error.message : "未知错误"),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, conversationId, selectedModel]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    },
    [sendMessage],
  );

  const handleNewConversation = useCallback(() => {
    const newId = generateId();
    localStorage.setItem("agent_conversation_id", newId);
    setConversationId(newId);
    setMessages([]);
  }, []);

  return (
    <div className="px-6 py-6 lg:px-8">
      <div className="mx-auto flex max-w-[960px] flex-col gap-4" style={{ height: "calc(100vh - 64px - 48px)" }}>
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-[18px] font-semibold text-text-primary">
              Agent 对话
            </h1>
            <p className="text-[13px] text-text-secondary">
              测试 RAG 检索 — 对话 ID: {conversationId.slice(0, 8)}...
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* 模型选择器 */}
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="h-[36px] rounded-lg border border-border bg-bg-surface px-3 text-[13px] text-text-primary outline-none focus:border-accent/40 transition-colors"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id} disabled={!m.available}>
                  {m.name} {m.available ? "" : "(未配置)"}
                </option>
              ))}
            </select>
            <button
              onClick={handleNewConversation}
              className="h-[36px] rounded-lg border border-border bg-bg-surface px-3 text-[13px] font-medium text-text-secondary hover:bg-bg-surface-hover transition-colors"
            >
              新对话
            </button>
          </div>
        </div>

        {/* Chat card */}
        <SectionCard className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
          >
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center space-y-3">
                  <div className="w-14 h-14 rounded-full bg-accent/10 flex items-center justify-center mx-auto">
                    <svg
                      width="28"
                      height="28"
                      viewBox="0 0 20 20"
                      fill="none"
                    >
                      <path
                        d="M3 4a1 1 0 011-1h10a1 1 0 011 1v8a1 1 0 01-1 1H7l-3 3v-3H4a1 1 0 01-1-1V4z"
                        stroke="#FF6B8A"
                        strokeWidth="1.5"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M6 7.5h6M6 10.5h4"
                        stroke="#FF6B8A"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                      />
                    </svg>
                  </div>
                  <p className="text-[14px] text-text-secondary">
                    开始与 Agent 对话，测试 RAG 检索效果
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-accent text-white"
                      : "bg-bg-surface-dim text-text-primary border border-border"
                  }`}
                >
                  <p className="text-[14px] leading-6 whitespace-pre-wrap">
                    {msg.content}
                  </p>
                  {msg.model && msg.role === "assistant" && (
                    <p className="text-[11px] text-text-muted mt-1">
                      via {msg.model}
                    </p>
                  )}
                  {msg.ragSources && msg.ragSources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-border/50">
                      <p className="text-[12px] font-semibold text-text-secondary mb-1.5">
                        RAG 参考来源
                      </p>
                      <div className="space-y-1.5">
                        {msg.ragSources.map((source, idx) => (
                          <div
                            key={idx}
                            className="rounded-lg bg-bg-surface px-3 py-2"
                          >
                            <p className="text-[12px] leading-5 text-text-secondary line-clamp-2">
                              {source.content}
                            </p>
                            <p className="text-[11px] text-accent/70 mt-1">
                              相关度: {(source.score * 100).toFixed(0)}%
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-bg-surface-dim border border-border rounded-2xl px-4 py-3 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-accent animate-bounce" />
                  <span
                    className="w-2 h-2 rounded-full bg-accent animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  />
                  <span
                    className="w-2 h-2 rounded-full bg-accent animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Input area */}
          <div className="border-t border-border px-4 py-3 shrink-0">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息测试 RAG 检索..."
                disabled={isLoading}
                className="flex-1 h-[44px] rounded-xl border border-border bg-bg-surface px-4 text-[14px] text-text-primary placeholder:text-text-muted outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/10 disabled:opacity-50 transition-colors"
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !input.trim()}
                className="h-[44px] w-[44px] rounded-xl bg-accent text-white flex items-center justify-center hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all shrink-0"
                aria-label="发送"
              >
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                  <path
                    d="M2 10l16-8-8 16-2-6-6-2z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
