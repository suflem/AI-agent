import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { ConfigProvider, theme as antdTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import {
  applyWebThemeCss,
  getWebTheme,
  listWebThemes,
  loadStoredTheme,
  persistTheme,
  type WebTheme,
} from "./themeRegistry";

type ThemeContextValue = {
  activeTheme: WebTheme;
  themeName: string;
  themes: WebTheme[];
  setThemeName: (name: string) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function useThemeState() {
  const [themeName, setThemeNameState] = useState(() => loadStoredTheme());

  const activeTheme = useMemo(() => getWebTheme(themeName), [themeName]);
  const themes = useMemo(() => listWebThemes(), []);

  useEffect(() => {
    applyWebThemeCss(activeTheme.name);
  }, [activeTheme.name]);

  const setThemeName = (name: string) => {
    const resolved = getWebTheme(name).name;
    persistTheme(resolved);
    setThemeNameState(resolved);
  };

  return { activeTheme, themeName: activeTheme.name, themes, setThemeName };
}

export function UiThemeProvider({ children }: PropsWithChildren) {
  const value = useThemeState();
  const algorithm = value.activeTheme.variant === "light" ? antdTheme.defaultAlgorithm : antdTheme.darkAlgorithm;
  const token = value.activeTheme.web?.antd;

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm,
          token: {
            colorPrimary: token?.colorPrimary ?? "#e8a257",
            colorBgBase: token?.colorBgBase ?? "#101218",
            colorTextBase: token?.colorTextBase ?? "#eef1f7",
            colorBorder: token?.colorBorder ?? "rgba(255,255,255,0.08)",
            borderRadius: 12,
            fontFamily:
              "\"ui-sans-serif\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", \"PingFang SC\", \"Hiragino Sans GB\", \"Microsoft YaHei\", \"Noto Sans SC\", \"Helvetica Neue\", Arial, sans-serif",
          },
        }}
      >
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useUiTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useUiTheme 必须在 UiThemeProvider 内使用");
  }
  return ctx;
}
