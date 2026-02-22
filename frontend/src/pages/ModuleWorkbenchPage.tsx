import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Wrench, User } from "lucide-react";
import { Button, Card, Empty, Select, Space, Tag, Typography } from "antd";
import { ApprovalDrawer } from "../components/ApprovalDrawer";
import { LoadingPulse } from "../components/LoadingPulse";
import { MarkdownContent } from "../components/MarkdownContent";
import { PageHero } from "../components/PageHero";
import { RobotMark } from "../components/RobotMark";
import { ToolForm } from "../components/ToolForm";
import { useToolRunner } from "../hooks/useToolRunner";
import { moduleByKey } from "../modules/registry";
import { useApprovalStore } from "../store/approvalStore";
import { toast } from "../services/toast";
import type { MotionMode } from "../theme/motionSettings";

type TimelineEntry = {
  id: string;
  role: "user" | "assistant" | "system";
  title: string;
  body: string;
  status?: "ok" | "needs_approval" | "error";
  isStreaming?: boolean;
};

function createEntry(entry: Omit<TimelineEntry, "id">): TimelineEntry {
  return { ...entry, id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}` };
}

function computeChunkSize(text: string) {
  if (text.length > 3200) return 84;
  if (text.length > 1600) return 56;
  if (text.length > 800) return 38;
  return 24;
}

const MODULE_SESSION_PREFIX = "ai_agent_module_session_v1";
const MAX_PERSISTED_ENTRIES = 120;

type SessionSnapshot = {
  actionId: string;
  timeline: TimelineEntry[];
  updatedAt: number;
};

function buildReadyEntry(title: string, summary: string): TimelineEntry {
  return createEntry({
    role: "assistant",
    title: `${title} 已就绪`,
    body: summary,
    status: "ok",
  });
}

function sanitizeTimelineForStorage(items: TimelineEntry[]): TimelineEntry[] {
  return items.slice(-MAX_PERSISTED_ENTRIES).map((item) => ({ ...item, isStreaming: false }));
}

function sessionStorageKey(moduleKey: string) {
  return `${MODULE_SESSION_PREFIX}:${moduleKey}`;
}

function stageLabel(stage: string) {
  if (stage === "dry-run") return "试运行中";
  if (stage === "confirm") return "审批确认中";
  return "思考中";
}

export function ModuleWorkbenchPage() {
  const { moduleKey = "" } = useParams();
  const moduleDef = moduleByKey[moduleKey];
  const runner = useToolRunner();
  const pendingApproval = useApprovalStore((s) => s.pending);
  const [actionId, setActionId] = useState("");
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [motionMode, setMotionMode] = useState<MotionMode>(() => {
    const raw = document.documentElement.dataset.motion;
    return raw === "reduced" || raw === "performance" || raw === "full" ? raw : "full";
  });
  const timelineWrapRef = useRef<HTMLDivElement | null>(null);
  const streamVersionRef = useRef(0);
  const streamTimerRef = useRef<number | null>(null);
  const storageKey = useMemo(() => sessionStorageKey(moduleKey), [moduleKey]);

  const stopStreaming = useCallback(() => {
    streamVersionRef.current += 1;
    if (streamTimerRef.current !== null) {
      window.clearTimeout(streamTimerRef.current);
      streamTimerRef.current = null;
    }
    setStreaming(false);
    setTimeline((prev) => prev.map((item) => (item.isStreaming ? { ...item, isStreaming: false } : item)));
  }, []);

  const appendStreamMessage = useCallback(
    async (entry: Omit<TimelineEntry, "id" | "body" | "isStreaming"> & { body: string }) => {
      stopStreaming();
      setStreaming(true);

      const version = streamVersionRef.current;
      const content = entry.body || "未返回响应内容。";
      const chunkSize = computeChunkSize(content);
      const streamEntryId = `${Date.now()}_${Math.random().toString(36).slice(2, 7)}_stream`;

      setTimeline((prev) => [
        ...prev,
        {
          id: streamEntryId,
          role: entry.role,
          title: entry.title,
          status: entry.status,
          body: "",
          isStreaming: true,
        },
      ]);

      await new Promise<void>((resolve) => {
        let cursor = 0;
        const tick = () => {
          if (streamVersionRef.current !== version) {
            streamTimerRef.current = null;
            resolve();
            return;
          }

          const nextCursor = Math.min(cursor + chunkSize, content.length);
          const nextBody = content.slice(0, nextCursor);
          const done = nextCursor >= content.length;

          setTimeline((prev) =>
            prev.map((item) => (item.id === streamEntryId ? { ...item, body: nextBody, isStreaming: !done } : item)),
          );

          cursor = nextCursor;
          if (done) {
            setStreaming(false);
            streamTimerRef.current = null;
            resolve();
            return;
          }

          streamTimerRef.current = window.setTimeout(tick, 14);
        };

        streamTimerRef.current = window.setTimeout(tick, 28);
      });
    },
    [stopStreaming],
  );

  const resetSession = useCallback(() => {
    if (!moduleDef) return;
    stopStreaming();
    setActionId(moduleDef.actions[0]?.id || "");
    setTimeline([buildReadyEntry(moduleDef.title, moduleDef.summary)]);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(storageKey);
    }
  }, [moduleDef, stopStreaming, storageKey]);

  useEffect(() => {
    if (!moduleDef?.actions.length) return;
    stopStreaming();

    if (typeof window !== "undefined") {
      try {
        const raw = window.localStorage.getItem(storageKey);
        if (raw) {
          const parsed = JSON.parse(raw) as SessionSnapshot;
          const restoredTimeline = Array.isArray(parsed.timeline)
            ? sanitizeTimelineForStorage(parsed.timeline)
            : [];
          const restoredAction = typeof parsed.actionId === "string" ? parsed.actionId : "";
          const actionExists = moduleDef.actions.some((action) => action.id === restoredAction);
          if (restoredTimeline.length > 0) {
            setTimeline(restoredTimeline);
            setActionId(actionExists ? restoredAction : moduleDef.actions[0].id);
            return;
          }
        }
      } catch {
        // ignore storage parse failures and fallback to fresh timeline
      }
    }

    setActionId(moduleDef.actions[0].id);
    setTimeline([buildReadyEntry(moduleDef.title, moduleDef.summary)]);
  }, [moduleDef, stopStreaming, storageKey]);

  useEffect(
    () => () => {
      stopStreaming();
    },
    [stopStreaming],
  );

  useEffect(() => {
    const onCancel = () => {
      stopStreaming();
      runner.cancelPending();
      toast.warning("操作已取消");
    };
    window.addEventListener("ai-agent:cancel-active", onCancel);
    return () => window.removeEventListener("ai-agent:cancel-active", onCancel);
  }, [runner.cancelPending, stopStreaming]);

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

  useEffect(() => {
    if (!moduleDef) return;
    if (typeof window === "undefined") return;
    try {
      const snapshot: SessionSnapshot = {
        actionId,
        timeline: sanitizeTimelineForStorage(timeline),
        updatedAt: Date.now(),
      };
      window.localStorage.setItem(storageKey, JSON.stringify(snapshot));
    } catch {
      // ignore storage write failures
    }
  }, [actionId, moduleDef, storageKey, timeline]);

  useEffect(() => {
    if (!timelineWrapRef.current) return;
    timelineWrapRef.current.scrollTop = timelineWrapRef.current.scrollHeight;
  }, [runner.loading, streaming, timeline]);

  const selectedAction = useMemo(
    () => moduleDef?.actions.find((action) => action.id === actionId) || moduleDef?.actions[0],
    [actionId, moduleDef],
  );

  if (!moduleDef) {
    return <Empty description={`未知模块：${moduleKey}`} />;
  }

  const runAction = async (args: Record<string, unknown>) => {
    if (!selectedAction) return;
    stopStreaming();

    setTimeline((prev) => [
      ...prev,
      createEntry({
        role: "user",
        title: selectedAction.name,
        body: JSON.stringify(args, null, 2) || "{}",
      }),
    ]);

    const output = await runner.execute(selectedAction.path, args);
    if (!output.ok) {
      await appendStreamMessage({
        role: "assistant",
        title: "执行失败",
        body: output.error,
        status: "error",
      });
      return;
    }

    if (output.data.status === "needs_approval") {
      await appendStreamMessage({
        role: "system",
        title: "需要审批",
        body: output.data.preview || "试运行已完成，请审批后继续。",
        status: "needs_approval",
      });
      return;
    }

    await appendStreamMessage({
      role: "assistant",
      title: "工具已执行",
      body: output.data.result || output.data.preview || "未返回响应内容。",
      status: output.data.status,
    });
  };

  const handleConfirm = async () => {
    stopStreaming();
    const output = await runner.confirmPending();
    if (!output.ok) {
      await appendStreamMessage({
        role: "assistant",
        title: "审批失败",
        body: output.error,
        status: "error",
      });
      return;
    }

    await appendStreamMessage({
      role: "assistant",
      title: "审批已确认",
      body: output.data.result || "审批后已执行工具。",
      status: output.data.status,
    });
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <PageHero
        icon={<RobotMark />}
        title={moduleDef.title}
        subtitle={moduleDef.summary}
        statusLabel="模块运行中"
      />

      <div className="module-grid">
        <Card className="panel-card" title="命令">
          <Space direction="vertical" style={{ width: "100%" }}>
            <Select
              className="command-select"
              value={selectedAction?.id}
              onChange={setActionId}
              options={moduleDef.actions.map((action) => ({
                value: action.id,
                label: action.name,
              }))}
            />
            <Typography.Paragraph type="secondary">{selectedAction?.description}</Typography.Paragraph>
            {selectedAction ? (
              <ToolForm fields={selectedAction.fields} loading={runner.loading} submitLabel="执行" onSubmit={runAction} />
            ) : (
              <Empty description="当前模块未配置操作。" />
            )}
            <div className="status-strip">
              <Typography.Text type="secondary">
                阶段：{stageLabel(runner.stage)} | 上下文：{timeline.length}
              </Typography.Text>
              <Space>
                {pendingApproval ? <Tag color="gold">待审批</Tag> : <Tag>无待审批</Tag>}
                {streaming ? <Tag color="processing">流式输出中</Tag> : null}
                <Button size="small" onClick={resetSession}>
                  清空会话
                </Button>
              </Space>
            </div>
          </Space>
        </Card>

        <Card className="panel-card" title="会话时间线">
          <div className="timeline-wrap" ref={timelineWrapRef}>
            <AnimatePresence initial={false}>
              {timeline.map((item) => (
                <motion.div
                  key={item.id}
                  layout
                  initial={{ opacity: 0, y: motionMode === "reduced" ? 0 : 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: motionMode === "reduced" ? 0 : -6 }}
                  transition={itemTransition}
                  className={`timeline-item timeline-item-enter timeline-${item.role}`}
                >
                  <div className="timeline-avatar">
                    {item.role === "assistant" ? <RobotMark compact /> : item.role === "user" ? <User size={16} /> : <Wrench size={16} />}
                  </div>
                  <div
                    className={`timeline-bubble ${item.isStreaming ? "timeline-bubble-streaming" : ""} ${
                      item.status === "error" ? "timeline-bubble-error" : ""
                    } ${item.status === "ok" ? "timeline-bubble-success" : ""} ${
                      item.status === "needs_approval" ? "timeline-bubble-warn" : ""
                    }`}
                  >
                    <div className="timeline-title-row">
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Space size={6}>
                        <Tag className="timeline-role-tag">
                          {item.role === "assistant" ? "助手区域" : item.role === "user" ? "用户区域" : "系统区域"}
                        </Tag>
                        {item.status ? (
                          <Tag color={item.status === "ok" ? "green" : item.status === "error" ? "red" : "gold"}>
                            {item.status === "ok" ? "成功" : item.status === "error" ? "错误" : "待审批"}
                          </Tag>
                        ) : null}
                      </Space>
                    </div>
                    <MarkdownContent content={item.body} className="timeline-body" />
                    {item.isStreaming ? <LoadingPulse compact label="流式输出中" showBar={false} /> : null}
                    {item.isStreaming ? <span className="stream-caret" aria-hidden /> : null}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            {runner.loading ? (
              <div className="timeline-item timeline-assistant">
                <div className="timeline-avatar">
                  <RobotMark compact />
                </div>
                <div className="timeline-bubble">
                  <LoadingPulse label={stageLabel(runner.stage)} detail={selectedAction?.name || moduleDef.title} />
                </div>
              </div>
            ) : null}
            {!runner.loading && timeline.length === 0 ? <Empty description="暂无执行记录。" /> : null}
          </div>
        </Card>
      </div>

      <ApprovalDrawer onConfirm={handleConfirm} onCancel={runner.cancelPending} loading={runner.loading && runner.stage === "confirm"} />
    </Space>
  );
}
