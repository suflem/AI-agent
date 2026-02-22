import { message, notification } from "antd";

type ToastType = "success" | "info" | "warning" | "error";

const DURATION = {
  success: 2.2,
  info: 2.5,
  warning: 3.4,
  error: 4.2,
} as const;

export const toast = {
  success(content: string) {
    void message.success({ content, duration: DURATION.success });
  },
  info(content: string) {
    void message.info({ content, duration: DURATION.info });
  },
  warning(content: string) {
    void message.warning({ content, duration: DURATION.warning });
  },
  error(content: string) {
    void message.error({ content, duration: DURATION.error });
  },
  notify(type: ToastType, title: string, description: string) {
    void notification[type]({
      message: title,
      description,
      duration: DURATION[type],
      placement: "bottomRight",
    });
  },
};

