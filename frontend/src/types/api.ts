export type ApprovalPayload = {
  dry_run?: boolean;
  confirm?: boolean;
  approval_id?: string;
  actor?: string;
};

export type ToolCallRequest = {
  args?: Record<string, unknown>;
  approval?: ApprovalPayload;
};

export type ToolDescriptor = {
  name?: string;
  path?: string;
  risk?: string;
  [key: string]: unknown;
};

export type ToolListResponse = {
  tools: ToolDescriptor[];
};

export type ToolCallResponse = {
  success: boolean;
  status: "ok" | "needs_approval" | "error";
  tool: string;
  result?: string;
  error?: string;
  approval_id?: string;
  preview?: string;
  duration_ms: number;
};

export type ApiResult<T> = {
  ok: boolean;
  data?: T;
  error?: string;
};
