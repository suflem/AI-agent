import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  MessageSquare,
  Settings,
  Blocks,
  Database,
  Zap,
  Search,
  Palette,
  Activity
} from "lucide-react";
import { Divider, Layout, Modal, Select, Tooltip, Typography } from "antd";
import { allModules } from "../modules/registry";
import { CommandPalette, type CommandEntry } from "../components/CommandPalette";
import { RobotMark } from "../components/RobotMark";
import { useUiTheme } from "../theme/ThemeContext";
import { applyMotionMode, listMotionModes, loadMotionMode, persistMotionMode, type MotionMode } from "../theme/motionSettings";

const { Header, Sider, Content } = Layout;
const COMMAND_USAGE_KEY = "ai-agent-command-usage-v1";

type CommandUsage = Record<string, { count: number; lastUsedAt: number }>;
type SideNavEntry = { key: string; label: string; group: string; icon?: ReactNode; description: string; shortcut?: string };

function loadUsage(): CommandUsage {
  try {
    const raw = localStorage.getItem(COMMAND_USAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as CommandUsage;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function persistUsage(next: CommandUsage) {
  localStorage.setItem(COMMAND_USAGE_KEY, JSON.stringify(next));
}

function fuzzyScore(query: string, text: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 0;
  const t = text.toLowerCase();

  let qi = 0;
  let score = 0;
  let streak = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti += 1) {
    if (t[ti] === q[qi]) {
      qi += 1;
      streak += 1;
      score += 3 + streak;
    } else {
      streak = 0;
      score -= 0.08;
    }
  }
  if (qi !== q.length) return -1;

  if (t.startsWith(q)) score += 10;
  if (t.includes(` ${q}`)) score += 4;
  score -= t.length * 0.01;
  return score;
}

function frecency(usage: CommandUsage[string] | undefined): number {
  if (!usage) return 0;
  const elapsedDays = Math.max(0, (Date.now() - usage.lastUsedAt) / (24 * 60 * 60 * 1000));
  const decay = Math.exp(-elapsedDays / 14);
  return usage.count * 5 * decay;
}

function makeShortcutList() {
  return [
    { keys: "/ | Ctrl/Cmd+K", desc: "打开命令面板" },
    { keys: "Ctrl/Cmd+L", desc: "清空当前会话" },
    { keys: "Ctrl/Cmd+N", desc: "新建会话" },
    { keys: "Esc", desc: "中断当前流式输出/操作" },
    { keys: "?", desc: "打开快捷键帮助" },
  ];
}

function routeTransitionForMode(mode: MotionMode) {
  if (mode === "reduced") {
    return { duration: 0.001 };
  }
  if (mode === "performance") {
    return { duration: 0.16, ease: [0.22, 0.78, 0.12, 1] as const };
  }
  return { duration: 0.26, ease: [0.2, 0.7, 0.1, 1] as const };
}

export function AppShell() {
  const { themeName, themes, setThemeName } = useUiTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [motionMode, setMotionMode] = useState<MotionMode>(() => loadMotionMode());
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [usageMap, setUsageMap] = useState<CommandUsage>(() => loadUsage());

  const commandEntries = useMemo<CommandEntry[]>(
    () => [
      {
        key: "/chat",
        label: "对话",
        description: "自然语言对话，支持工具执行。",
        group: "core",
        icon: <MessageSquare size={16} />,
        shortcut: "Ctrl+L",
      },
      {
        key: "/system",
        label: "系统",
        description: "健康检查、冒烟测试与工具注册表。",
        group: "core",
        icon: <Settings size={16} />,
        shortcut: "Ctrl+Shift+S",
      },
      ...allModules.map((moduleDef) => ({
        key: `/modules/${moduleDef.key}`,
        label: moduleDef.title,
        description: moduleDef.summary,
        group: "module",
        icon: <Blocks size={16} />,
        shortcut: undefined,
      })),
    ],
    [],
  );

  const sideNavEntries = useMemo<SideNavEntry[]>(
    () =>
      commandEntries.map((entry) => ({
        ...entry,
        icon:
          entry.icon || (entry.group === "module" ? <Blocks size={16} /> : <Database size={16} />),
      })),
    [commandEntries],
  );

  const groupedSideNav = useMemo(
    () => ({
      core: sideNavEntries.filter((entry) => entry.group === "core"),
      modules: sideNavEntries.filter((entry) => entry.group === "module"),
    }),
    [sideNavEntries],
  );

  const themeOptions = useMemo(
    () =>
      themes.map((item) => {
        const swatch = item.web?.antd?.colorPrimary || item.web?.css_vars?.["--accent"] || "#e8a257";
        return {
          value: item.name,
          label: (
            <span className="theme-option-label">
              <span className="theme-option-swatch" style={{ backgroundColor: swatch }} />
              <span>{item.label}</span>
            </span>
          ),
        };
      }),
    [themes],
  );

  const filteredCommands = useMemo(() => {
    const query = paletteQuery.trim().toLowerCase();
    if (!query) {
      return [...commandEntries]
        .map((entry) => ({
          ...entry,
          recentScore: frecency(usageMap[entry.key]),
        }))
        .sort((a, b) => (b.recentScore || 0) - (a.recentScore || 0));
    }
    return commandEntries
      .map((entry) => {
        const target = `${entry.label} ${entry.description} ${entry.key} ${entry.group}`.toLowerCase();
        const score = fuzzyScore(query, target);
        return {
          ...entry,
          recentScore: frecency(usageMap[entry.key]),
          __score: score,
        };
      })
      .filter((entry) => entry.__score >= 0)
      .sort((a, b) => {
        if (b.__score !== a.__score) return b.__score - a.__score;
        return (b.recentScore || 0) - (a.recentScore || 0);
      })
      .map(({ __score, ...entry }) => entry);
  }, [commandEntries, paletteQuery, usageMap]);

  const closePalette = useCallback(() => {
    setPaletteOpen(false);
    setPaletteQuery("");
    setActiveIndex(0);
  }, []);

  const openPalette = useCallback(() => {
    setPaletteOpen(true);
  }, []);

  const selectRoute = useCallback(
    (path: string) => {
      setUsageMap((prev) => {
        const current = prev[path] || { count: 0, lastUsedAt: 0 };
        const next = {
          ...prev,
          [path]: {
            count: current.count + 1,
            lastUsedAt: Date.now(),
          },
        };
        persistUsage(next);
        return next;
      });
      navigate(path);
      closePalette();
    },
    [closePalette, navigate],
  );

  const trackUsage = useCallback((path: string) => {
    setUsageMap((prev) => {
      const current = prev[path] || { count: 0, lastUsedAt: 0 };
      const next = {
        ...prev,
        [path]: {
          count: current.count + 1,
          lastUsedAt: Date.now(),
        },
      };
      persistUsage(next);
      return next;
    });
  }, []);

  useEffect(() => {
    setActiveIndex(0);
  }, [paletteOpen, paletteQuery]);

  useEffect(() => {
    closePalette();
  }, [closePalette, location.pathname]);

  useEffect(() => {
    applyMotionMode(motionMode);
    persistMotionMode(motionMode);
  }, [motionMode]);

  useEffect(() => {
    const isTypingElement = (target: EventTarget | null) => {
      if (!(target instanceof HTMLElement)) return false;
      return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const typing = isTypingElement(event.target);

      if (paletteOpen) {
        if (event.key === "Escape") {
          event.preventDefault();
          closePalette();
          return;
        }

        if (event.key === "ArrowDown") {
          event.preventDefault();
          setActiveIndex((prev) => (filteredCommands.length ? (prev + 1) % filteredCommands.length : 0));
          return;
        }

        if (event.key === "ArrowUp") {
          event.preventDefault();
          setActiveIndex((prev) => (filteredCommands.length ? (prev - 1 + filteredCommands.length) % filteredCommands.length : 0));
          return;
        }

        if (event.key === "Enter") {
          if (filteredCommands.length > 0) {
            event.preventDefault();
            const target = filteredCommands[Math.min(activeIndex, filteredCommands.length - 1)];
            selectRoute(target.key);
          }
          return;
        }
        return;
      }

      if (event.key === "Escape") {
        window.dispatchEvent(new CustomEvent("ai-agent:cancel-active"));
      }

      const slashTrigger = event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey && !typing;
      const commandTrigger = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
      const clearChatTrigger = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "l" && !typing;
      const newChatTrigger = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n" && !typing;
      const shortcutHelpTrigger = event.key === "?" && !typing;

      if (slashTrigger || commandTrigger) {
        event.preventDefault();
        openPalette();
        return;
      }

      if (clearChatTrigger) {
        event.preventDefault();
        navigate("/chat");
        window.dispatchEvent(new CustomEvent("ai-agent:chat-clear"));
        return;
      }

      if (newChatTrigger) {
        event.preventDefault();
        navigate("/chat");
        window.dispatchEvent(new CustomEvent("ai-agent:chat-new"));
        return;
      }

      if (shortcutHelpTrigger) {
        event.preventDefault();
        setHelpOpen(true);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeIndex, closePalette, filteredCommands, navigate, openPalette, paletteOpen, selectRoute]);

  const selectedKey =
    location.pathname.startsWith("/modules/") || location.pathname === "/system" || location.pathname === "/chat"
      ? location.pathname
      : "/chat";
  const pageTitle =
    location.pathname === "/chat"
      ? "对话"
      : location.pathname === "/system"
        ? "系统运维"
        : "模块工作台";
  const pageSubtitle =
    location.pathname === "/chat"
      ? "流式对话与工具执行"
      : location.pathname === "/system"
        ? "诊断、冒烟检查与运行时可观测性"
        : "可组合模块与审批流";

  return (
    <Layout className="app-layout">
      <div className="app-shell-aura" aria-hidden>
        <span className="aura-blob aura-blob-a" />
        <span className="aura-blob aura-blob-b" />
        <span className="aura-blob aura-blob-c" />
      </div>
      <Sider width={260} breakpoint="lg" collapsedWidth={0} className="app-sider">
        <div className="brand-block">
          <div className="brand-row">
            <RobotMark />
            <div>
              <Typography.Title level={5} style={{ margin: 0, fontWeight: 600 }}>
                AI Agent
              </Typography.Title>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                智能控制台
              </Typography.Text>
            </div>
          </div>
        </div>
        <nav className="side-nav" aria-label="模块导航">
          <Typography.Text className="side-nav-group-label">核心</Typography.Text>
          {groupedSideNav.core.map((entry) => (
            <Tooltip key={entry.key} title={entry.description} placement="right">
              <Link
                to={entry.key}
                onClick={() => trackUsage(entry.key)}
                className={selectedKey === entry.key ? "side-nav-link side-nav-link-active" : "side-nav-link"}
              >
                <span className="side-nav-icon">{entry.icon}</span>
                <span className="side-nav-label">{entry.label}</span>
              </Link>
            </Tooltip>
          ))}
          <Divider className="side-nav-divider" />
          <Typography.Text className="side-nav-group-label">模块</Typography.Text>
          {groupedSideNav.modules.map((entry) => (
            <Tooltip key={entry.key} title={entry.description} placement="right">
              <Link
                to={entry.key}
                onClick={() => trackUsage(entry.key)}
                className={selectedKey === entry.key ? "side-nav-link side-nav-link-active" : "side-nav-link"}
              >
                <span className="side-nav-icon">{entry.icon}</span>
                <span className="side-nav-label">{entry.label}</span>
              </Link>
            </Tooltip>
          ))}
        </nav>
        <div className="sider-footer">
          <div className="sider-settings">
            <Select
              value={themeName}
              onChange={setThemeName}
              options={themeOptions}
              size="small"
              className="theme-select-sidebar"
              suffixIcon={<Palette size={14} />}
              dropdownMatchSelectWidth={false}
              placement="topRight"
            />
            <Select
              value={motionMode}
              onChange={(value) => setMotionMode(value as MotionMode)}
              options={listMotionModes()}
              size="small"
              className="motion-select-sidebar"
              suffixIcon={<Activity size={14} />}
              dropdownMatchSelectWidth={false}
              placement="topRight"
            />
          </div>
          <div className="sider-status">
            <div className="sider-status-row">
              <Database size={13} />
              <span>本地运行时</span>
            </div>
            <div className="sider-status-row">
              <Zap size={13} />
              <span>界面版本 v0.4</span>
            </div>
          </div>
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <div className="header-row">
            <div className="header-title-area">
              <Typography.Text strong className="header-title">
                {pageTitle}
              </Typography.Text>
              <Typography.Text type="secondary" className="header-subtitle">
                {pageSubtitle}
              </Typography.Text>
            </div>
            <button type="button" className="command-trigger" onClick={openPalette}>
              <Search size={13} />
              <span>搜索命令</span>
              <kbd className="kbd-chip">⌘K</kbd>
            </button>
          </div>
        </Header>
        <Content className="app-content">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              className="route-scene"
              initial={{ opacity: 0, y: motionMode === "reduced" ? 0 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: motionMode === "reduced" ? 0 : -4 }}
              transition={routeTransitionForMode(motionMode)}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </Content>
      </Layout>
      <CommandPalette
        open={paletteOpen}
        query={paletteQuery}
        entries={filteredCommands}
        activeIndex={Math.min(activeIndex, Math.max(filteredCommands.length - 1, 0))}
        onQueryChange={setPaletteQuery}
        onActiveIndexChange={setActiveIndex}
        onClose={closePalette}
        onSelect={selectRoute}
      />
      <Modal
        open={helpOpen}
        title="快捷键"
        footer={null}
        onCancel={() => setHelpOpen(false)}
        className="shortcut-help-modal"
      >
        <div className="shortcut-help-list">
          {makeShortcutList().map((item) => (
            <div key={item.keys} className="shortcut-help-item">
              <kbd className="kbd-chip">{item.keys}</kbd>
              <Typography.Text type="secondary">{item.desc}</Typography.Text>
            </div>
          ))}
        </div>
      </Modal>
    </Layout>
  );
}
