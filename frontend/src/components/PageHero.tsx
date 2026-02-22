import type { ReactNode } from "react";
import { Card, Space, Tag, Typography } from "antd";

type PageHeroProps = {
  icon: ReactNode;
  title: string;
  subtitle: string;
  statusLabel?: string;
  statusColor?: string;
  extra?: ReactNode;
};

export function PageHero({
  icon,
  title,
  subtitle,
  statusLabel,
  statusColor = "gold",
  extra,
}: PageHeroProps) {
  return (
    <Card className="panel-card page-hero-card">
      <div className="page-hero-row">
        <Space size={12} align="start">
          <span className="page-hero-icon">{icon}</span>
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {title}
            </Typography.Title>
            <Typography.Text type="secondary">{subtitle}</Typography.Text>
          </div>
        </Space>
        <Space size={8} wrap>
          {extra}
          {statusLabel ? (
            <Tag color={statusColor} className="page-hero-tag">
              {statusLabel}
            </Tag>
          ) : null}
        </Space>
      </div>
    </Card>
  );
}

