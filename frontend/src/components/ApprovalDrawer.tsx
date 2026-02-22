import { Button, Drawer, Space, Typography } from "antd";
import { LoadingPulse } from "./LoadingPulse";
import { RobotMark } from "./RobotMark";
import { useApprovalStore } from "../store/approvalStore";

type ApprovalDrawerProps = {
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
};

export function ApprovalDrawer({ onConfirm, onCancel, loading = false }: ApprovalDrawerProps) {
  const pending = useApprovalStore((s) => s.pending);
  return (
    <Drawer
      title={
        <Space>
          <RobotMark compact />
          <span>需要审批</span>
        </Space>
      }
      open={Boolean(pending)}
      onClose={onCancel}
      width={520}
      rootClassName="approval-drawer"
      extra={
        <Space>
          <Button onClick={onCancel} ghost>
            取消
          </Button>
          <Button type="primary" onClick={onConfirm} loading={loading} className="accent-btn">
            确认执行
          </Button>
        </Space>
      }
    >
      {pending ? (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Typography.Text type="secondary">接口路径：{pending.path}</Typography.Text>
          <Typography.Paragraph>
            审批 ID：<Typography.Text code>{pending.approvalId}</Typography.Text>
          </Typography.Paragraph>
          <Typography.Title level={5}>试运行预览</Typography.Title>
          <pre className="result-text">{pending.preview || "没有返回预览内容。"}</pre>
          {loading ? <LoadingPulse label="提交审批确认" /> : null}
        </Space>
      ) : null}
    </Drawer>
  );
}
