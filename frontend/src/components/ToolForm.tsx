import { useEffect, useMemo } from "react";
import { Button, Form, Input, InputNumber, Space, Switch, Typography } from "antd";
import type { FieldSchema } from "../types/ui";
import { toast } from "../services/toast";

type ToolFormProps = {
  fields: FieldSchema[];
  onSubmit: (args: Record<string, unknown>) => Promise<void> | void;
  submitLabel?: string;
  loading?: boolean;
};

function buildInitialValues(fields: FieldSchema[]) {
  const result: Record<string, unknown> = {};
  for (const field of fields) {
    if (field.defaultValue !== undefined) {
      result[field.key] = field.defaultValue;
    }
  }
  return result;
}

export function ToolForm({ fields, onSubmit, submitLabel = "执行", loading = false }: ToolFormProps) {
  const [form] = Form.useForm();
  const initialValues = useMemo(() => buildInitialValues(fields), [fields]);

  useEffect(() => {
    form.resetFields();
    form.setFieldsValue(initialValues);
  }, [form, initialValues]);

  const handleFinish = async (values: Record<string, unknown>) => {
    const parsed: Record<string, unknown> = {};
    for (const field of fields) {
      const value = values[field.key];
      if (value === undefined || value === null || value === "") {
        continue;
      }
      if (field.type === "json" && typeof value === "string") {
        try {
          parsed[field.key] = JSON.parse(value);
        } catch {
          toast.error(`字段「${field.label}」的 JSON 格式无效`);
          return;
        }
      } else {
        parsed[field.key] = value;
      }
    }
    await onSubmit(parsed);
  };

  return (
    <Form form={form} layout="vertical" initialValues={initialValues} onFinish={handleFinish} className="tool-form">
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        {fields.map((field) => (
          <Form.Item
            key={field.key}
            label={field.label}
            name={field.key}
            valuePropName={field.type === "boolean" ? "checked" : "value"}
            rules={field.required ? [{ required: true, message: `请填写「${field.label}」` }] : undefined}
            extra={field.helperText}
          >
            {field.type === "textarea" ? (
              <Input.TextArea rows={field.rows || 4} placeholder={field.placeholder} />
            ) : field.type === "number" ? (
              <InputNumber min={field.min} max={field.max} style={{ width: "100%" }} placeholder={field.placeholder} />
            ) : field.type === "boolean" ? (
              <Switch />
            ) : field.type === "json" ? (
              <Input.TextArea rows={field.rows || 6} placeholder={field.placeholder || "{\"key\":\"value\"}"} />
            ) : (
              <Input placeholder={field.placeholder} />
            )}
          </Form.Item>
        ))}
      </Space>
      {fields.length === 0 && <Typography.Text type="secondary">该操作无需参数。</Typography.Text>}
      <Form.Item style={{ marginTop: 16, marginBottom: 0 }}>
        <Button type="primary" htmlType="submit" loading={loading} className="accent-btn">
          {submitLabel}
        </Button>
      </Form.Item>
    </Form>
  );
}
