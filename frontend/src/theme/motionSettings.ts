export type MotionMode = "full" | "performance" | "reduced";

export const MOTION_STORAGE_KEY = "ai-agent-motion-mode";

const DEFAULT_MOTION_MODE: MotionMode = "full";

export function listMotionModes(): Array<{ value: MotionMode; label: string }> {
  return [
    { value: "full", label: "动效：完整" },
    { value: "performance", label: "动效：性能优先" },
    { value: "reduced", label: "动效：精简" },
  ];
}

export function loadMotionMode(): MotionMode {
  const raw = localStorage.getItem(MOTION_STORAGE_KEY);
  if (raw === "full" || raw === "performance" || raw === "reduced") {
    return raw;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return "reduced";
  }
  return DEFAULT_MOTION_MODE;
}

export function persistMotionMode(mode: MotionMode): void {
  localStorage.setItem(MOTION_STORAGE_KEY, mode);
}

export function applyMotionMode(mode: MotionMode): void {
  document.documentElement.dataset.motion = mode;
  window.dispatchEvent(new CustomEvent<MotionMode>("ai-agent:motion-mode", { detail: mode }));
}
