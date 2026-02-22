# Frontend UI Console

React + TypeScript + Vite frontend for the modular backend API.

## Visual Direction

- Neumorphism + Material Design hybrid style
  - soft dual-shadow (convex/concave) for cards, buttons, inputs
  - Material elevation layers, ripple animations, smooth motion
  - medium-dark neumorphic surfaces with subtle gradient overlays
  - animated aura background blobs for ambient depth
- 5 built-in themes with full CSS variable support:
  - **OpenCode Night** (default) — warm amber accent on blue-grey
  - **Terminal Ice** — cool cyan accent on slate-blue
  - **Copper Drive** — warm copper accent on brown-earth
  - **Mint Matrix** — green accent on dark teal
  - **Paper Terminal** — light theme, blue accent on warm paper
- theme-aware `--tint` system: all overlays, scrollbars, ripples, and tag backgrounds adapt automatically between dark and light themes
- robot mark and timeline conversation layout
- custom loading pulse for dry-run and confirm stages
- command palette (`/` or `Ctrl/Cmd+K`) for keyboard-first navigation
- streamed timeline output for assistant/system messages
- module session persistence (last conversation restore + context continuity)
- memory center (global/topic memory + vector memory operations)
- skill studio (visual scaffold parameters + backend AI-assisted code generation)
- lazy route loading + vendor manual chunks for smoother navigation/build output

## Quick Start

1. Install deps

```bash
cd frontend
npm.cmd install
```

2. Start backend (from project root)

```bash
venv\Scripts\python.exe run_api.py --host 127.0.0.1 --port 8000
```

3. Start frontend

```bash
npm.cmd run dev
```

PowerShell users: if `npm` is blocked by execution policy, use `npm.cmd` or switch terminal to `cmd.exe`.
If install fails with `EPERM`, close running `node`/`electron` processes and reinstall with:

```bash
npm.cmd install --cache .npm-cache
```

If `npm.cmd run dev` fails with `Error: spawn EPERM`, run:

```bash
taskkill /F /IM node.exe
taskkill /F /IM electron.exe
powershell -Command "Unblock-File .\node_modules\@esbuild\win32-x64\esbuild.exe"
npm.cmd run dev
```

## Environment

- `VITE_API_BASE` (optional): override API base, default `http://127.0.0.1:8000/api`
- `VITE_ROUTER_MODE` (optional): `hash` for Electron file protocol build
- `VITE_BASE_PATH` (optional): `./` for Electron static asset path

## Architecture

- `src/app/`: app shell (header, sidebar, aura background) and routing
- `src/pages/`: route pages (`system`, `chat`, `module workbench`)
- `src/modules/registry.ts`: module/action schema registry
- `src/components/`: reusable UI blocks (`PageHero`, `CommandPalette`, `MarkdownContent`, etc.)
- `src/store/`: Zustand state (`approvalStore`)
- `src/services/apiClient.ts`: API request + approval calls
- `src/hooks/useToolRunner.ts`: action execution orchestration
- `src/types/`: backend and UI shared types
- `src/styles/global.css`: all neumorphism + Material Design CSS (~1900 lines)
- `src/theme/opencode_themes.json`: 5 theme definitions with CSS variables
- `src/theme/themeRegistry.ts`: theme loading, application, and persistence

## Theming

All visual tokens are CSS custom properties set in `:root` and overridden per-theme via `opencode_themes.json`.

Key variable groups:
- `--bg-main`, `--surface-0..4`: background and surface layers
- `--text-main`, `--text-soft`, `--text-dim`: three-tier text hierarchy
- `--tint`: `255,255,255` (dark) or `0,0,0` (light) — used as `rgba(var(--tint), opacity)` for theme-aware overlays
- `--text-on-accent`: text color on accent-colored buttons
- `--neu-light`, `--neu-dark`: neumorphic shadow pair
- `--neu-convex`, `--neu-concave`, `--neu-flat`: pre-composed shadow tokens
- `--elevation-material-1..3`: Material Design elevation layers
- `--accent`, `--accent-strong`: primary accent colors
- `--scrollbar-thumb`, `--selection-bg`: scrollbar and text selection colors

To add a new theme, add an entry to `opencode_themes.json` with all CSS vars and Ant Design token overrides.

## New Modules

- `Memory Center`
  - use existing tool gateway to manage `save_memory/read_memory/list_memories`
  - operate vector memory via `rag_save/rag_search/rag_status`
  - inspect `memories/chat_history/latest.json` quickly from UI
- `Skill Studio`
  - visual parameter form for tool/module metadata + params JSON
  - preview scaffold with `skill_scaffold_preview`
  - create scaffold with `skill_scaffold_create` (approval required)
  - optional backend AI completion for function body, with deterministic fallback template

## Approval Flow

All tool execution uses two-step flow:

1. Call endpoint with `approval.dry_run=true`
2. If response is `needs_approval`, show preview and approval id in `ApprovalDrawer`
3. Confirm with `approval.confirm=true` and `approval.approval_id`

## Extending a Module

Add a new action in `src/modules/registry.ts`:

- Set `path` to backend endpoint (`/study/pack`, `/grad/compare`, etc.)
- Define argument fields (`text`, `textarea`, `number`, `boolean`, `json`)
- The generic `ToolForm` and execution panel work automatically

## Desktop EXE (Electron)

1. Build Windows installer:

```bash
cd frontend
npm.cmd install
npm.cmd run build:electron
```

2. Output directory:

- `frontend/release/AI-Agent-Setup-0.1.0.exe`

3. Runtime requirement:

- Backend API still needs to run on `http://127.0.0.1:8000` (or override `VITE_API_BASE` before build)
