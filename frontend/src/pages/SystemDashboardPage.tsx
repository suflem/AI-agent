import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Col, Row, Segmented, Skeleton, Space, Tag, Typography } from "antd";
import { ApprovalDrawer } from "../components/ApprovalDrawer";
import { LoadingPulse } from "../components/LoadingPulse";
import { PageHero } from "../components/PageHero";
import { ResultPanel } from "../components/ResultPanel";
import { RobotMark } from "../components/RobotMark";
import { useToolRunner } from "../hooks/useToolRunner";
import { getHealth, listTools } from "../services/apiClient";

type HealthLevel = "quick" | "full";

export function SystemDashboardPage() {
  const [healthLevel, setHealthLevel] = useState<HealthLevel>("full");
  const runner = useToolRunner();

  const healthQuery = useQuery({
    queryKey: ["system-health", healthLevel],
    queryFn: () => getHealth(healthLevel),
  });

  const toolsQuery = useQuery({
    queryKey: ["tool-list"],
    queryFn: listTools,
  });

  const healthResponse = healthQuery.data?.ok ? healthQuery.data.data : null;
  const healthError = healthQuery.data && !healthQuery.data.ok ? healthQuery.data.error || "健康检查失败" : "";

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <PageHero
        icon={<RobotMark />}
        title="系统运维"
        subtitle="API 诊断、冒烟测试与工具可见性。"
        statusLabel="运行中"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card className="panel-card" title="健康检查">
            <Space direction="vertical" style={{ width: "100%" }}>
              <Segmented
                options={[
                  { label: "快速", value: "quick" },
                  { label: "完整", value: "full" },
                ]}
                value={healthLevel}
                onChange={(value) => setHealthLevel(value as HealthLevel)}
                block
              />
              <Button onClick={() => healthQuery.refetch()} loading={healthQuery.isFetching} className="accent-btn">
                刷新健康状态
              </Button>
            </Space>
            <div style={{ marginTop: 16 }}>
              <ResultPanel
                title="健康结果"
                loading={healthQuery.isLoading || healthQuery.isFetching}
                response={healthResponse}
                apiError={healthError}
                emptyText="尚未加载健康结果。"
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="panel-card" title="冒烟测试">
            <Typography.Paragraph type="secondary">
              试运行 + 审批流，与模块页共用同一执行管线。
            </Typography.Paragraph>
            <Button
              type="primary"
              onClick={() => runner.execute("/system/smoke", { cleanup: true })}
              loading={runner.loading}
              className="accent-btn"
            >
              执行冒烟测试
            </Button>
            <div style={{ marginTop: 16 }}>
              <ResultPanel response={runner.result} loading={runner.loading} apiError={runner.error} />
            </div>
          </Card>
        </Col>
      </Row>

      <Card className="panel-card" title="工具注册表">
        {toolsQuery.isLoading ? (
          <div className="chat-skeleton">
            <Skeleton active paragraph={{ rows: 2 }} />
            <LoadingPulse compact label="加载注册表" showBar={false} />
          </div>
        ) : !toolsQuery.data?.ok ? (
          <Typography.Text type="danger">{toolsQuery.data?.error || "工具列表加载失败"}</Typography.Text>
        ) : (
          <pre className="result-text">{JSON.stringify(toolsQuery.data.data, null, 2)}</pre>
        )}
      </Card>

      <ApprovalDrawer onConfirm={runner.confirmPending} onCancel={runner.cancelPending} loading={runner.loading} />
    </Space>
  );
}
