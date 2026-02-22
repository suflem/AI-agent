export type FieldType = "text" | "textarea" | "number" | "boolean" | "json";

export type FieldSchema = {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  helperText?: string;
  defaultValue?: unknown;
  rows?: number;
  min?: number;
  max?: number;
};

export type ModuleAction = {
  id: string;
  name: string;
  description: string;
  path: string;
  fields: FieldSchema[];
};

export type UiModule = {
  key: string;
  title: string;
  summary: string;
  actions: ModuleAction[];
};
