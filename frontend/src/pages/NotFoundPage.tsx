import { Button, Card, Space, Typography } from "antd";
import { Link } from "react-router-dom";
import { RobotMark } from "../components/RobotMark";

export function NotFoundPage() {
  return (
    <Card className="panel-card">
      <Space direction="vertical" size="middle">
        <Space>
          <RobotMark />
          <Typography.Title level={3} style={{ margin: 0 }}>
            页面不存在
          </Typography.Title>
        </Space>
        <Typography.Text type="secondary">你访问的页面在当前控制台中不存在。</Typography.Text>
        <Button type="primary" className="accent-btn">
          <Link to="/system">返回系统页</Link>
        </Button>
      </Space>
    </Card>
  );
}
