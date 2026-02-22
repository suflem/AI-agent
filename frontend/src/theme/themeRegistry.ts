import themesData from "./opencode_themes.json";

type RawTheme = {
  name: string;
  label: string;
  variant: "dark" | "light";
  web: {
    css_vars: Record<string, string>;
    antd: {
      colorPrimary: string;
      colorBgBase: string;
      colorTextBase: string;
      colorBorder: string;
    };
  };
};

type RawRegistry = {
  version: number;
  default_theme: string;
  themes: RawTheme[];
};

const registry = themesData as RawRegistry;

export type WebTheme = RawTheme;

export const THEME_STORAGE_KEY = "ai-agent-web-theme";

export function listWebThemes(): WebTheme[] {
  return Array.isArray(registry.themes) ? registry.themes : [];
}

export function defaultThemeName(): string {
  return registry.default_theme || "opencode_night";
}

export function getWebTheme(name: string): WebTheme {
  const found = listWebThemes().find((item) => item.name === name);
  if (found) return found;
  const fallback = listWebThemes().find((item) => item.name === defaultThemeName());
  if (fallback) return fallback;
  return {
    name: "opencode_night",
    label: "夜幕代码",
    variant: "dark",
    web: {
      css_vars: {},
      antd: {
        colorPrimary: "#d4975a",
        colorBgBase: "#1e2233",
        colorTextBase: "#dfe3ef",
        colorBorder: "rgba(255,255,255,0.04)",
      },
    },
  };
}

export function applyWebThemeCss(themeName: string): WebTheme {
  const theme = getWebTheme(themeName);
  const vars = theme.web?.css_vars ?? {};
  const root = document.documentElement;
  Object.entries(vars).forEach(([k, v]) => {
    root.style.setProperty(k, v);
  });
  root.dataset.theme = theme.name;
  root.dataset.themeVariant = theme.variant;
  return theme;
}

export function loadStoredTheme(): string {
  const raw = localStorage.getItem(THEME_STORAGE_KEY) || "";
  const stored = raw.trim();
  if (stored) return stored;

  const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
  const targetVariant = prefersLight ? "light" : "dark";
  const variantTheme = listWebThemes().find((item) => item.variant === targetVariant);
  return variantTheme?.name || defaultThemeName();
}

export function persistTheme(themeName: string): void {
  localStorage.setItem(THEME_STORAGE_KEY, themeName);
}
