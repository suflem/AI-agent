import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  Copy,
  Edit2,
  File,
  FileText,
  Paperclip,
  RotateCw,
  Wrench,
  User,
} from "lucide-react";
import { Button, Card, Input, Skeleton, Space, Tag, Typography } from "antd";
import { MarkdownContent } from "../components/MarkdownContent";
import { LoadingPulse } from "../components/LoadingPulse";
import { PageHero } from "../components/PageHero";
import { RobotMark } from "../components/RobotMark";
import { toast } from "../services/toast";
import type { MotionMode } from "../theme/motionSettings";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  payload?: string;
  toolName?: string;
  status?: "streaming" | "done" | "error";
  createdAt: number;
};

type TimelineItem = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  payload?: string;
  toolName?: string;
  status?: "streaming" | "done" | "error";
  isPlaceholder?: boolean;
  createdAt: number;
};

const ESTIMATED_ROW_HEIGHT = 170;
const OVERSCAN_ROWS = 7;
const VIRTUAL_THRESHOLD = 32;
const CHAT_INPUT_MAX = 4000;
const ATTACHMENT_TEXT_MAX_CHARS = 8000;
const ATTACHMENT_TEXT_MAX_BYTES = 240 * 1024;

type ChatCommand = {
  key: string;
  summary: string;
};

type AttachmentItem = {
  id: string;
  name: string;
  size: number;
  type: string;
  kind: "text" | "binary" | "unsupported";
  previewText?: string;
  truncated?: boolean;
  error?: string;
};

function uid() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function toText(data: unknown): string {
  if (typeof data === "string") return data;
  if (data == null) return "";
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function compactText(input: unknown, max = 42): string {
  const raw = String(input ?? "").replace(/\s+/g, " ").trim();
  if (!raw) return "";
  return raw.length > max ? `${raw.slice(0, max - 3)}...` : raw;
}

function mapToolStage(toolName: unknown, args: Record<string, unknown> | null | undefined): { label: string; detail: string } {
  const tool = String(toolName || "").trim();
  const a = args || {};
  const lcTool = tool.toLowerCase();
  const query = compactText(a.query ?? a.keyword ?? a.pattern);
  const target = compactText(a.kb_name ?? a.source_path ?? a.filename ?? a.path ?? a.url ?? a.command);

  if (
    lcTool.includes("search")
    || lcTool.includes("grep")
    || lcTool.includes("find")
    || lcTool.includes("query")
  ) {
    return {
      label: query ? `检索（${query}）` : "检索",
      detail: tool,
    };
  }
  if (lcTool.includes("build") || lcTool.includes("scaffold")) {
    return {
      label: target ? `构建（${target}）` : "构建",
      detail: tool,
    };
  }
  if (lcTool.includes("fetch") || lcTool.includes("read")) {
    return {
      label: target ? `读取（${target}）` : "读取",
      detail: tool,
    };
  }
  if (lcTool.includes("write") || lcTool.includes("edit") || lcTool.includes("create")) {
    return {
      label: target ? `编辑（${target}）` : "编辑",
      detail: tool,
    };
  }
  return {
    label: tool ? tool.replace(/_/g, " ") : "执行",
    detail: query || target,
  };
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function isLikelyTextFile(file: File): boolean {
  if (file.type.startsWith("text/")) return true;
  const name = file.name.toLowerCase();
  return [
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".csv",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".java",
    ".go",
    ".rs",
    ".sql",
    ".log",
    ".ini",
  ].some((ext) => name.endsWith(ext));
}

function attachmentToContext(item: AttachmentItem): string {
  const header = `- ${item.name} (${formatBytes(item.size)})`;
  if (item.kind === "text" && item.previewText) {
    const suffix = item.truncated ? "\n[内容已截断]" : "";
    return `${header}\n\`\`\`text\n${item.previewText}\n\`\`\`${suffix}`;
  }
  if (item.error) return `${header}\n[错误] ${item.error}`;
  return `${header}\n[二进制或不支持的文件，仅附带元信息]`;
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [loadingLabel, setLoadingLabel] = useState("思考中");
  const [loadingDetail, setLoadingDetail] = useState("");
  const [motionMode, setMotionMode] = useState<MotionMode>(() => {
    const raw = document.documentElement.dataset.motion;
    return raw === "reduced" || raw === "performance" || raw === "full" ? raw : "full";
  });
  const abortControllerRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoFollow, setAutoFollow] = useState(true);
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 0 });
  const [commandIndex, setCommandIndex] = useState(0);
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [dragOver, setDragOver] = useState(false);

  const timelineItems = useMemo<TimelineItem[]>(() => {
    const base = messages.map((m) => ({ ...m }));
    if (loading && messages[messages.length - 1]?.status !== "streaming") {
      base.push({
        id: "__loading__",
        role: "assistant",
        content: "",
        status: "streaming",
        isPlaceholder: true,
        createdAt: Date.now(),
      });
    }
    return base;
  }, [loading, messages]);

  const virtualEnabled = timelineItems.length >= VIRTUAL_THRESHOLD;

  const recalcVirtualRange = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const count = timelineItems.length;
    if (!count) {
      setVisibleRange({ start: 0, end: 0 });
      return;
    }
    if (!virtualEnabled) {
      setVisibleRange({ start: 0, end: count - 1 });
      return;
    }
    const viewHeight = Math.max(1, el.clientHeight);
    const scrollTop = Math.max(0, el.scrollTop);
    const start = Math.max(0, Math.floor(scrollTop / ESTIMATED_ROW_HEIGHT) - OVERSCAN_ROWS);
    const viewportRows = Math.ceil(viewHeight / ESTIMATED_ROW_HEIGHT) + OVERSCAN_ROWS * 2;
    const end = Math.min(count - 1, start + viewportRows);
    setVisibleRange({ start, end });
  }, [timelineItems.length, virtualEnabled]);

  const syncAutoFollow = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - (el.scrollTop + el.clientHeight) < 140;
    setAutoFollow(nearBottom);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      syncAutoFollow();
      recalcVirtualRange();
    };
    el.addEventListener("scroll", onScroll);
    recalcVirtualRange();
    return () => el.removeEventListener("scroll", onScroll);
  }, [recalcVirtualRange, syncAutoFollow]);

  useEffect(() => {
    recalcVirtualRange();
    if (!autoFollow) return;
    const el = scrollRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: timelineItems.length > 2 ? "smooth" : "auto" });
      recalcVirtualRange();
    });
  }, [autoFollow, loading, recalcVirtualRange, timelineItems.length]);

  const clearChat = useCallback((notify = false) => {
    setMessages([]);
    setSessionId("");
    setVisibleRange({ start: 0, end: 0 });
    setAutoFollow(true);
    setLoading(false);
    setLoadingLabel("思考中");
    setLoadingDetail("");
    setAttachments([]);
    setDragOver(false);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (notify) toast.info("会话已清空");
  }, []);

  const cancelActive = useCallback(() => {
    if (!abortControllerRef.current) return;
    abortControllerRef.current.abort();
    toast.warning("已中断流式输出");
  }, []);

  useEffect(() => {
    const onClear = () => clearChat(true);
    const onNew = () => clearChat(false);
    const onCancel = () => cancelActive();
    window.addEventListener("ai-agent:chat-clear", onClear);
    window.addEventListener("ai-agent:chat-new", onNew);
    window.addEventListener("ai-agent:cancel-active", onCancel);
    return () => {
      window.removeEventListener("ai-agent:chat-clear", onClear);
      window.removeEventListener("ai-agent:chat-new", onNew);
      window.removeEventListener("ai-agent:cancel-active", onCancel);
    };
  }, [cancelActive, clearChat]);

  useEffect(
    () => () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    },
    [],
  );

  useEffect(() => {
    const onMode = (event: Event) => {
      const value = (event as CustomEvent<MotionMode>).detail;
      if (value === "reduced" || value === "performance" || value === "full") {
        setMotionMode(value);
      }
    };
    window.addEventListener("ai-agent:motion-mode", onMode);
    return () => window.removeEventListener("ai-agent:motion-mode", onMode);
  }, []);

  const itemTransition =
    motionMode === "reduced"
      ? { duration: 0.001 }
      : motionMode === "performance"
        ? { duration: 0.14, ease: [0.22, 0.78, 0.12, 1] as const }
        : { duration: 0.2, ease: [0.2, 0.7, 0.1, 1] as const };

  const inlineCommands = useMemo<ChatCommand[]>(
    () => [
      { key: "/clear", summary: "清空当前会话" },
      { key: "/new", summary: "新建会话" },
      { key: "/stop", summary: "停止当前流式请求" },
      { key: "/attach", summary: "打开文件选择器" },
      { key: "/help", summary: "查看命令帮助" },
    ],
    [],
  );

  const commandSuggestions = useMemo(() => {
    const raw = input.trim();
    if (!raw.startsWith("/")) return [];
    const query = raw.toLowerCase();
    return inlineCommands.filter((cmd) => cmd.key.includes(query));
  }, [inlineCommands, input]);

  useEffect(() => {
    setCommandIndex(0);
  }, [input]);

  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const ingestFiles = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    const nextItems: AttachmentItem[] = [];
    for (const file of files) {
      const base: AttachmentItem = {
        id: uid(),
        name: file.name,
        size: file.size,
        type: file.type,
        kind: "binary",
      };
      if (isLikelyTextFile(file)) {
        if (file.size > ATTACHMENT_TEXT_MAX_BYTES) {
          nextItems.push({
            ...base,
            kind: "unsupported",
            error: `文本文件超过 ${formatBytes(ATTACHMENT_TEXT_MAX_BYTES)} 的内联限制`,
          });
          continue;
        }
        try {
          const text = await file.text();
          const truncated = text.length > ATTACHMENT_TEXT_MAX_CHARS;
          nextItems.push({
            ...base,
            kind: "text",
            previewText: truncated ? `${text.slice(0, ATTACHMENT_TEXT_MAX_CHARS)}\n...[truncated]` : text,
            truncated,
          });
        } catch {
          nextItems.push({
            ...base,
            kind: "unsupported",
            error: "读取文件失败",
          });
        }
        continue;
      }
      nextItems.push(base);
    }
    setAttachments((prev) => [...prev, ...nextItems]);
    toast.info(`已附加 ${nextItems.length} 个文件`);
  }, []);

  const onFileInputChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const fileList = event.target.files;
      if (!fileList?.length) return;
      const files = Array.from(fileList);
      await ingestFiles(files);
      event.target.value = "";
    },
    [ingestFiles],
  );

  const onDropFiles = useCallback(
    async (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragOver(false);
      const files = Array.from(event.dataTransfer.files || []);
      await ingestFiles(files);
    },
    [ingestFiles],
  );

  const buildFinalMessage = useCallback(
    (baseText: string) => {
      if (!attachments.length) return baseText;
      const header = "[附加文件上下文]";
      const body = attachments.map((item) => attachmentToContext(item)).join("\n\n");
      const prefix = baseText || "请分析附加文件，并给出简洁结论。";
      return `${prefix}\n\n${header}\n${body}`;
    },
    [attachments],
  );

  const runMessage = useCallback(async (payloadText: string, displayText?: string) => {
    if (!payloadText || loading) return;

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setMessages((prev) => [
      ...prev,
      {
        id: uid(),
        role: "user",
        content: displayText || payloadText,
        payload: payloadText,
        status: "done",
        createdAt: Date.now(),
      },
    ]);
    setLoading(true);
    setLoadingLabel("路由请求");
    setLoadingDetail("创建流会话");

    const assistantId = uid();
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", status: "streaming", createdAt: Date.now() }]);

    try {
      const resp = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: payloadText, auto_approve: false }),
        signal: abortController.signal,
      });

      if (!resp.ok || !resp.body) {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: `HTTP ${resp.status}`, status: "error" as const } : m)),
        );
        setLoading(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const raw = line.slice(6);
            try {
              const data = JSON.parse(raw);

              if (eventType === "session") {
                setSessionId(data.session_id || "");
                setLoadingLabel("会话已连接");
                setLoadingDetail((data.session_id || "").slice(0, 12));
              } else if (eventType === "token") {
                setLoadingLabel("生成回复");
                setLoadingDetail("流式输出中");
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: m.content + (data.text || "") } : m,
                  ),
                );
              } else if (eventType === "tool_start") {
                const stage = mapToolStage(data.tool, (data.args as Record<string, unknown>) || {});
                setLoadingLabel(stage.label);
                setLoadingDetail(stage.detail);
                setMessages((prev) => [
                  ...prev,
                  {
                    id: uid(),
                    role: "tool",
                    content: `工具开始执行\n\n名称：${String(data.tool || "未知工具")}`,
                    toolName: String(data.tool || "工具"),
                    status: "streaming",
                    createdAt: Date.now(),
                  },
                ]);
              } else if (eventType === "tool_result") {
                const stage = mapToolStage(data.tool, undefined);
                setLoadingLabel(`${stage.label} 完成`);
                setLoadingDetail(String(data.tool || "工具"));
                setMessages((prev) => {
                  const idx = [...prev].reverse().findIndex((m) => m.role === "tool" && m.toolName === data.tool);
                  if (idx === -1) {
                    return [
                      ...prev,
                      {
                        id: uid(),
                        role: "tool",
                        content: toText(data.result),
                        toolName: data.tool,
                        status: "done",
                        createdAt: Date.now(),
                      },
                    ];
                  }
                  const realIdx = prev.length - 1 - idx;
                  return prev.map((m, i) => (i === realIdx ? { ...m, content: toText(data.result), status: "done" as const } : m));
                });
              } else if (eventType === "approval_required") {
                const stage = mapToolStage(data.tool, (data.args as Record<string, unknown>) || {});
                setLoadingLabel(`${stage.label} 需要审批`);
                setLoadingDetail(String(data.tool || "工具"));
                setMessages((prev) => [
                  ...prev,
                  {
                    id: uid(),
                    role: "tool",
                    content: `工具 ${data.tool} 需要审批。请在 CLI 中审批，或启用 auto_approve。`,
                    toolName: data.tool,
                    status: "error",
                    createdAt: Date.now(),
                  },
                ]);
              } else if (eventType === "done") {
                setLoadingLabel("已完成");
                setLoadingDetail("");
                setMessages((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, status: "done" as const } : m)),
                );
              } else if (eventType === "error") {
                setLoadingLabel("流输出错误");
                setLoadingDetail("请查看下方详情");
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: m.content + `\n\n错误：${data.message}`, status: "error" as const } : m,
                  ),
                );
              }
            } catch {
              // ignore parse errors
            }
            eventType = "";
          }
        }
      }

      // Ensure streaming state is cleared
      setMessages((prev) =>
        prev.map((m) => (m.status === "streaming" ? { ...m, status: "done" as const } : m)),
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId || m.content));
      } else {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: `网络错误：${err}`, status: "error" as const } : m)),
        );
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
      setLoadingLabel("思考中");
      setLoadingDetail("");
    }
  }, [loading, sessionId]);

  const executeInlineCommand = useCallback(
    (value: string): boolean => {
      const cmd = value.trim().toLowerCase();
      if (!cmd.startsWith("/")) return false;
      if (cmd === "/clear") {
        clearChat(true);
        setInput("");
        return true;
      }
      if (cmd === "/new") {
        clearChat(false);
        setInput("");
        return true;
      }
      if (cmd === "/stop") {
        cancelActive();
        setInput("");
        return true;
      }
      if (cmd === "/attach") {
        openFilePicker();
        setInput("");
        return true;
      }
      if (cmd === "/help") {
        toast.info("聊天命令：/clear、/new、/stop、/attach、/help");
        setInput("");
        return true;
      }
      return false;
    },
    [cancelActive, clearChat, openFilePicker],
  );

  const sendMessage = useCallback(() => {
    const text = input.trim();
    if ((!text && attachments.length === 0) || loading) return;
    if (executeInlineCommand(text)) return;
    const finalMessage = buildFinalMessage(text);
    const displayMessage =
      attachments.length > 0
        ? `${text || "分析附加文件"}\n\n[已附加 ${attachments.length} 个文件]\n${attachments.map((item) => `- ${item.name} (${formatBytes(item.size)})`).join("\n")}`
        : finalMessage;
    setInput("");
    setAttachments([]);
    void runMessage(finalMessage, displayMessage);
  }, [attachments, buildFinalMessage, executeInlineCommand, input, loading, runMessage]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (commandSuggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setCommandIndex((prev) => (prev + 1) % commandSuggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setCommandIndex((prev) => (prev - 1 + commandSuggestions.length) % commandSuggestions.length);
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const selected = commandSuggestions[Math.min(commandIndex, commandSuggestions.length - 1)];
        if (selected) {
          executeInlineCommand(selected.key);
        }
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const copyMessage = useCallback(async (msg: TimelineItem) => {
    const text = (msg.payload || msg.content).trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast.success("消息已复制");
    } catch {
      toast.error("复制消息失败");
    }
  }, []);

  const retryMessage = useCallback(
    (msg: TimelineItem) => {
      if (loading) return;
      const text = (msg.payload || msg.content).trim();
      if (!text) return;
      void runMessage(text);
      toast.info("已重新提交请求");
    },
    [loading, runMessage],
  );

  const editMessage = useCallback((msg: TimelineItem) => {
    setInput(msg.payload || msg.content);
  }, []);

  const roleLabel = (role: TimelineItem["role"]) => {
    if (role === "assistant") return "助手";
    if (role === "user") return "用户";
    return "工具";
  };

  const renderTimelineContent = (msg: TimelineItem) => (
    <>
      <div className="timeline-avatar">
        {msg.role === "assistant" ? <RobotMark compact /> : msg.role === "user" ? <User size={16} /> : <Wrench size={16} />}
      </div>
      <div
        className={`timeline-bubble ${msg.status === "streaming" ? "timeline-bubble-streaming" : ""} ${
          msg.role === "tool" && msg.status === "streaming" ? "timeline-tool-running" : ""
        } ${msg.status === "error" ? "timeline-bubble-error" : ""} ${
          msg.status === "done" && msg.role === "tool" ? "timeline-bubble-success" : ""
        }`}
      >
        {!msg.isPlaceholder ? (
          <div className="timeline-title-row">
            <Typography.Text strong>{msg.role === "tool" ? msg.toolName || "工具" : roleLabel(msg.role)}</Typography.Text>
            <Space size={6}>
              <Typography.Text className="timeline-time">{formatTime(msg.createdAt)}</Typography.Text>
              <Tag className="timeline-role-tag">{msg.role === "tool" ? "工具输出" : `${roleLabel(msg.role)}输出`}</Tag>
              {msg.status === "streaming" ? (
                <Tag color="processing">流式输出</Tag>
              ) : msg.status === "error" ? (
                <Tag color="red">错误</Tag>
              ) : null}
            </Space>
          </div>
        ) : null}

        {msg.content ? <MarkdownContent content={msg.content} className="timeline-body" /> : msg.status === "streaming" ? <LoadingPulse label={loadingLabel} detail={loadingDetail} /> : null}
        {msg.status === "streaming" && msg.content ? <LoadingPulse compact label={loadingLabel} detail={loadingDetail} showBar={false} /> : null}
        {msg.status === "streaming" && msg.content ? <span className="stream-caret" aria-hidden /> : null}
        {!msg.isPlaceholder ? (
          <div className="timeline-actions">
            <Button size="small" type="text" icon={<Copy size={14} />} onClick={() => void copyMessage(msg)}>
              复制
            </Button>
            {msg.role === "user" ? (
              <>
                <Button size="small" type="text" icon={<Edit2 size={14} />} onClick={() => editMessage(msg)}>
                  编辑
                </Button>
                <Button size="small" type="text" icon={<RotateCw size={14} />} onClick={() => retryMessage(msg)} disabled={loading}>
                  重试
                </Button>
              </>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );

  const renderTimelineItem = (msg: TimelineItem) => {
    const className = `timeline-item timeline-item-enter timeline-${msg.role === "tool" ? "system" : msg.role}`;
    if (virtualEnabled) {
      return (
        <div key={msg.id} className={className}>
          {renderTimelineContent(msg)}
        </div>
      );
    }
    return (
      <motion.div
        key={msg.id}
        layout
        initial={{ opacity: 0, y: motionMode === "reduced" ? 0 : 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: motionMode === "reduced" ? 0 : -6 }}
        transition={itemTransition}
        className={className}
      >
        {renderTimelineContent(msg)}
      </motion.div>
    );
  };

  const rangeStart = virtualEnabled ? visibleRange.start : 0;
  const rangeEnd = virtualEnabled ? visibleRange.end : Math.max(0, timelineItems.length - 1);
  const safeStart = Math.min(Math.max(0, rangeStart), Math.max(0, timelineItems.length - 1));
  const safeEnd = Math.min(Math.max(safeStart, rangeEnd), Math.max(0, timelineItems.length - 1));
  const visibleItems = timelineItems.length ? timelineItems.slice(safeStart, safeEnd + 1) : [];
  const topSpacer = virtualEnabled ? safeStart * ESTIMATED_ROW_HEIGHT : 0;
  const bottomSpacer = virtualEnabled ? Math.max(0, (timelineItems.length - safeEnd - 1) * ESTIMATED_ROW_HEIGHT) : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%", gap: 16 }}>
      <PageHero
        icon={<RobotMark />}
        title="对话"
        subtitle="自然语言交互，支持工具执行与实时流反馈。"
        statusLabel={sessionId ? `会话 ${sessionId.slice(0, 8)}` : "新会话"}
        extra={
          <Space>
            <Button type="text" size="small" onClick={() => clearChat(true)}>
              新建会话
            </Button>
            {loading ? (
              <Button type="text" size="small" danger onClick={cancelActive}>
                停止
              </Button>
            ) : null}
          </Space>
        }
      />

      <Card className={`panel-card chat-card ${dragOver ? "chat-card-drop-active" : ""}`.trim()}>
        <input ref={fileInputRef} type="file" multiple onChange={(event) => void onFileInputChange(event)} className="chat-file-input" />
        <div
          className="timeline-wrap chat-timeline"
          ref={scrollRef}
          onDragOver={(event) => {
            event.preventDefault();
            if (!dragOver) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => void onDropFiles(event)}
        >
          {messages.length === 0 && loading ? (
            <div className="chat-skeleton" style={{ maxWidth: 900, margin: "0 auto", width: "100%" }}>
              <Skeleton active avatar paragraph={{ rows: 2 }} />
              <Skeleton active avatar paragraph={{ rows: 2 }} />
            </div>
          ) : messages.length === 0 && !loading ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}>
              <RobotMark />
              <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
                开始对话吧。我可以调用工具、编辑文件、管理任务等。
              </Typography.Paragraph>
            </div>
          ) : (
            <>
              {topSpacer > 0 ? <div className="timeline-spacer" style={{ height: topSpacer }} aria-hidden /> : null}
              {virtualEnabled ? visibleItems.map((item) => renderTimelineItem(item)) : <AnimatePresence initial={false}>{visibleItems.map((item) => renderTimelineItem(item))}</AnimatePresence>}
              {bottomSpacer > 0 ? <div className="timeline-spacer" style={{ height: bottomSpacer }} aria-hidden /> : null}
            </>
          )}
        </div>
        {dragOver ? <div className="chat-drop-hint">拖拽文件到这里即可附加</div> : null}

        {attachments.length > 0 ? (
          <div className="chat-attachments">
            {attachments.map((item) => (
              <div key={item.id} className="chat-attachment-item">
                <span className="chat-attachment-icon">{item.kind === "text" ? <FileText size={16} /> : <File size={16} />}</span>
                <span className="chat-attachment-main">
                  <span className="chat-attachment-name">{item.name}</span>
                  <span className="chat-attachment-meta">
                    {formatBytes(item.size)}
                    {item.error ? ` · ${item.error}` : item.kind === "text" && item.truncated ? " · 已截断" : ""}
                  </span>
                </span>
                <Button
                  size="small"
                  type="text"
                  icon={<X size={14} />}
                  onClick={() => removeAttachment(item.id)}
                  aria-label={`移除 ${item.name}`}
                />
              </div>
            ))}
          </div>
        ) : null}

        {commandSuggestions.length > 0 ? (
          <div className="chat-command-list">
            {commandSuggestions.map((cmd, idx) => (
              <button
                key={cmd.key}
                type="button"
                className={idx === commandIndex ? "chat-command-item chat-command-item-active" : "chat-command-item"}
                onMouseEnter={() => setCommandIndex(idx)}
                onClick={() => executeInlineCommand(cmd.key)}
              >
                <span>{cmd.key}</span>
                <span>{cmd.summary}</span>
              </button>
            ))}
          </div>
        ) : null}

        <div className="chat-input-row">
          <Button
            type="default"
            icon={<Paperclip size={18} />}
            onClick={openFilePicker}
            className="chat-attach-btn"
          />
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="给 AI Agent 发消息...（Shift+Enter 换行）"
            autoSize={{ minRows: 1, maxRows: 8 }}
            className="chat-input"
            maxLength={CHAT_INPUT_MAX}
            disabled={loading}
          />
          <Button type="primary" onClick={sendMessage} loading={loading} className="accent-btn" shape="round">
            发送
          </Button>
        </div>
      </Card>
    </div>
  );
}
