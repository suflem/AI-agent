# UI Module Architecture

## Visual Design System

Neumorphism + Material Design hybrid:
- Convex shadows (raised): cards, buttons, avatars
- Concave shadows (inset): inputs, code blocks, blockquotes
- Flat shadows (subtle): tags, hover states, secondary elements
- Material elevation layers (1-3) stacked with neumorphic shadows
- Material ripple animation on buttons and interactive elements
- Animated aura background blobs for ambient depth
- Theme-aware `--tint` system for automatic dark/light adaptation

5 themes defined in `src/theme/opencode_themes.json`, applied via CSS custom properties.

## Implemented Route Layer

1. `system`
- path: `/system`
- health check, smoke test, tool registry

2. `modules/:moduleKey`
- path: `/modules/study|academic|grad|feed|memory|skill_studio|daily_notify`
- unified schema-driven workbench page

## Configuration Layer

- `src/modules/registry.ts`
- each module contains multiple actions:
  - `path`: backend endpoint
  - `fields`: argument schema for dynamic rendering

## State Layer

- Query cache: TanStack Query (`system health`, `tool list`)
- UI state: Zustand (`approvalStore` for pending approval requests)
- Session memory: localStorage snapshot per module (action + timeline restore)

## Component Layer

- `PageHero`: page header card with icon, title, subtitle, status tag
- `RobotMark`: robot identity mark used in shell/timeline/drawer
- `LoadingPulse`: unified loading animation for dry-run/confirm stages
- `CommandPalette`: keyboard-first route navigation (`/`, `Ctrl/Cmd+K`)
- `ToolForm`: render args form from schema
- `ResultPanel`: response panel for system pages
- `MarkdownContent`: markdown renderer with syntax highlighting and code copy
- `ApprovalDrawer`: display preview and confirm approval
- `Conversation Timeline`: assistant/user/system execution history with streamed output, neumorphic bubble styling, and role-based avatar treatment
- `Memory Center` module: memory/rag/chat-history actions via generic tool gateway
- `Skill Studio` module: visual scaffold generation + backend AI-assisted code completion

## Approval Interaction

1. run dry-run request (`approval.dry_run=true`)
2. if `needs_approval`, open drawer and display preview
3. user confirms to execute with `approval.confirm=true` and `approval_id`

## Performance Path

- route-level lazy loading in `src/app/router.tsx`
- manual chunk strategy in `vite.config.ts` to split react/antd/query/state vendors

## Style Architecture

- Single CSS file: `src/styles/global.css` (~1900 lines)
- All tokens in `:root`, overridden per-theme via JSON config
- No duplicate selectors — base rules include Material + Neumorphic properties
- Separate sections for: aura background, page hero, Material ripple, keyframes
- Responsive breakpoints at 768px and 1080px
