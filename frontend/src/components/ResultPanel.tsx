import { Card, Empty, Space, Tag, Typography } from "antd";
import type { ToolCallResponse } from "../types/api";
import { LoadingPulse } from "./LoadingPulse";
import { MarkdownContent } from "./MarkdownContent";

type ResultPanelProps = {
  title?: string;
  response?: ToolCallResponse | null;
  loading?: boolean;
  apiError?: string;
  emptyText?: string;
};

function statusColor(status: ToolCallResponse["status"]) {
  if (status === "ok") return "green";
  if (status === "needs_approval") return "orange";
  return "red";
}

function statusLabel(status: ToolCallResponse["status"]) {
  if (status === "ok") return "成功";
  if (status === "needs_approval") return "待审批";
  return "错误";
}

export function ResultPanel({
  title = "执行结果",
  response,
  loading = false,
  apiError = "",
  emptyText = "执行一个操作后即可查看输出。",
}: ResultPanelProps) {
  const statusClass = response?.status ? `result-panel-status-${response.status}` : "";
  return (
    <Card className={`panel-card ${statusClass}`.trim()} title={title}>
      {loading ? (
        <LoadingPulse label="处理中" detail="整理预览与结果" />
      ) : apiError ? (
        <Typography.Text type="danger">{apiError}</Typography.Text>
      ) : response ? (
        <Space direction="vertical" size="small" style={{ width: "100%" }}>
          <Space className="result-meta-row">
            <Tag color={statusColor(response.status)}>{statusLabel(response.status)}</Tag>
            <Tag>{response.tool || "工具"}</Tag>
            <Tag>{response.duration_ms} 毫秒</Tag>
          </Space>
          {response.preview ? (
            <div className="result-section result-section-preview">
              <Typography.Text className="result-section-title">预览</Typography.Text>
              <MarkdownContent content={response.preview} />
            </div>
          ) : null}
          {response.result ? (
            <div className="result-section result-section-main">
              <Typography.Text className="result-section-title">结果</Typography.Text>
              <MarkdownContent content={response.result} />
            </div>
          ) : null}
          {response.error ? (
            <div className="result-section result-section-error">
              <Typography.Text className="result-section-title">错误</Typography.Text>
              <MarkdownContent content={response.error} />
            </div>
          ) : null}
        </Space>
      ) : (
        <Empty description={emptyText} />
      )}
    </Card>
  );
}
