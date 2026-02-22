import { type ReactNode } from "react";
import { Input, Modal, Typography } from "antd";

export type CommandEntry = {
  key: string;
  label: string;
  description: string;
  group: string;
  icon?: ReactNode;
  shortcut?: string;
  recentScore?: number;
};

type CommandPaletteProps = {
  open: boolean;
  query: string;
  entries: CommandEntry[];
  activeIndex: number;
  onQueryChange: (value: string) => void;
  onActiveIndexChange: (index: number) => void;
  onClose: () => void;
  onSelect: (path: string) => void;
};

export function CommandPalette({
  open,
  query,
  entries,
  activeIndex,
  onQueryChange,
  onActiveIndexChange,
  onClose,
  onSelect,
}: CommandPaletteProps) {
  const groupLabel = (group: string) => {
    if (group === "core") return "核心";
    if (group === "module") return "模块";
    return group;
  };

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={660} centered className="command-palette-modal" closable={false}>
      <div className="command-palette-wrap">
        <Input
          autoFocus
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="输入命令或路由..."
          className="command-palette-input"
        />
        <div className="command-palette-list" role="listbox" aria-label="命令面板列表">
          {entries.length === 0 ? (
            <Typography.Text type="secondary">没有匹配的命令。</Typography.Text>
          ) : (
            entries.map((entry, index) => (
              <button
                key={entry.key}
                type="button"
                className={index === activeIndex ? "command-item command-item-active" : "command-item"}
                onMouseEnter={() => onActiveIndexChange(index)}
                onClick={() => onSelect(entry.key)}
              >
                <span className="command-item-main">
                  <span className="command-item-label">
                    {entry.icon ? <span className="command-item-icon">{entry.icon}</span> : null}
                    <span>{entry.label}</span>
                  </span>
                  <span className="command-item-meta">
                    {entry.shortcut ? <kbd className="kbd-chip command-kbd">{entry.shortcut}</kbd> : null}
                    <span className="command-item-group">{groupLabel(entry.group)}</span>
                  </span>
                </span>
                <span className="command-item-desc">{entry.description}</span>
              </button>
            ))
          )}
        </div>
        <div className="command-palette-foot">
          <Typography.Text type="secondary">Enter：打开</Typography.Text>
          <Typography.Text type="secondary">方向键：选择</Typography.Text>
          <Typography.Text type="secondary">Esc：关闭</Typography.Text>
        </div>
      </div>
    </Modal>
  );
}
