import { useCallback, useState } from "react";
import type { ToolCallResponse } from "../types/api";
import { confirmTool, dryRunTool } from "../services/apiClient";
import { useApprovalStore } from "../store/approvalStore";
import { toast } from "../services/toast";

type RunnerArgs = Record<string, unknown>;
type RunnerStage = "idle" | "dry-run" | "confirm";
type RunnerOutcome = { ok: true; data: ToolCallResponse } | { ok: false; error: string };

export function useToolRunner() {
  const [result, setResult] = useState<ToolCallResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<RunnerStage>("idle");
  const pending = useApprovalStore((s) => s.pending);
  const setPending = useApprovalStore((s) => s.setPending);
  const clearPending = useApprovalStore((s) => s.clearPending);

  const execute = useCallback(
    async (path: string, args: RunnerArgs): Promise<RunnerOutcome> => {
      setLoading(true);
      setStage("dry-run");
      setError("");

      const preview = await dryRunTool(path, args);
      if (!preview.ok || !preview.data) {
        const message = preview.error || "试运行失败";
        setError(message);
        toast.error(message);
        setLoading(false);
        setStage("idle");
        return { ok: false, error: message };
      }

      setResult(preview.data);
      if (preview.data.status === "needs_approval" && preview.data.approval_id) {
        toast.info("需要审批确认");
        setPending({
          path,
          args,
          approvalId: preview.data.approval_id,
          preview: preview.data.preview,
        });
      } else {
        toast.success("工具执行完成");
        clearPending();
      }
      setLoading(false);
      setStage("idle");
      return { ok: true, data: preview.data };
    },
    [clearPending, setPending],
  );

  const confirmPending = useCallback(async (): Promise<RunnerOutcome> => {
    if (!pending) {
      return { ok: false, error: "当前没有待审批项" };
    }
    setLoading(true);
    setStage("confirm");
    setError("");
    const confirmed = await confirmTool(pending.path, pending.args, pending.approvalId);
    if (!confirmed.ok || !confirmed.data) {
      const message = confirmed.error || "审批确认失败";
      setError(message);
      toast.error(message);
      setLoading(false);
      setStage("idle");
      return { ok: false, error: message };
    }
    setResult(confirmed.data);
    toast.success("审批已确认");
    clearPending();
    setLoading(false);
    setStage("idle");
    return { ok: true, data: confirmed.data };
  }, [clearPending, pending]);

  const cancelPending = useCallback(() => {
    clearPending();
    toast.warning("已取消待审批请求");
  }, [clearPending]);

  return { result, error, loading, stage, execute, confirmPending, cancelPending };
}
