import type { ApiResult, ToolCallRequest, ToolCallResponse, ToolListResponse } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";

async function requestJson<T>(url: string, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const resp = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      ...init,
    });
    const bodyText = await resp.text();
    const data = bodyText ? (JSON.parse(bodyText) as T) : undefined;
    if (!resp.ok) {
      return { ok: false, error: `请求失败（HTTP ${resp.status}）` };
    }
    if (!data) {
      return { ok: false, error: "响应体为空" };
    }
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: `请求异常：${String(err)}` };
  }
}

export function getHealth(level: "quick" | "full" = "full") {
  return requestJson<ToolCallResponse>(`${API_BASE}/system/health?level=${level}`);
}

export function listTools() {
  return requestJson<ToolListResponse>(`${API_BASE}/tool/list`);
}

export function postTool(path: string, payload: ToolCallRequest) {
  return requestJson<ToolCallResponse>(`${API_BASE}${path}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function dryRunTool(path: string, args: Record<string, unknown>) {
  return postTool(path, {
    args,
    approval: { dry_run: true, confirm: false, actor: "ui" },
  });
}

export function confirmTool(path: string, args: Record<string, unknown>, approvalId: string) {
  return postTool(path, {
    args,
    approval: {
      dry_run: false,
      confirm: true,
      approval_id: approvalId,
      actor: "ui",
    },
  });
}

export function postSmoke(cleanup = true) {
  return dryRunTool("/system/smoke", { cleanup });
}

export async function callWithApproval(path: string, args: Record<string, unknown>) {
  return dryRunTool(path, args);
}
