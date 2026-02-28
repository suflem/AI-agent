# AI Agent Modular Platform

一个面向学习、科研与日常任务管理的本地 AI Agent 工程项目。  
项目提供 `CLI`、`TUI`、`Web`、`Electron` 四类入口，后端采用“工具注册 + 模块化 API + 风险审批流”架构，支持快速扩展与稳定交付。

## Core Features

- 工具系统模块化：自动发现并注册技能工具（当前健康检查显示 `78` 个工具）。
- 统一 API 网关：按业务域拆分路由，支持 `30+` 接口端点。
- 风险工具审批：`dry-run -> approval_id -> confirm` 双阶段执行机制。
- 多模型 Provider：兼容 OpenAI 风格接口（Moonshot/OpenAI/DeepSeek/OpenRouter/Gemini）。
- 本地记忆能力：JSON 数据持久化 + ChromaDB 向量检索。
- 多端交互：FastAPI 后端联动 React 前端，并可打包 Electron 客户端。

## Tech Stack

- Backend: `Python`, `FastAPI`, `Uvicorn`
- Runtime/UI: `openai`, `Rich`, `Textual`
- Storage: `JSON`, `ChromaDB`
- Frontend: `React 18`, `TypeScript`, `Vite`, `Ant Design`, `Zustand`, `Framer Motion`
- Desktop: `Electron`, `electron-builder`

## Quick Start

### 1) Install Backend Dependencies

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

在 `.env` 中配置至少一个可用的 API Key（如 `KIMI_API_KEY` / `OPENAI_API_KEY`）。

### 2) Start API Server

```bash
venv\Scripts\python.exe run_api.py --host 127.0.0.1 --port 8000
```

- API Docs: `http://127.0.0.1:8000/docs`
- API Root: `http://127.0.0.1:8000/`

### 3) Start Frontend

```bash
cd frontend
npm.cmd install
npm.cmd run dev
```

- Frontend URL: `http://127.0.0.1:5173`

## Common Commands

```bash
# CLI
venv\Scripts\python.exe run.py

# TUI
venv\Scripts\python.exe run.py --tui

# Runtime Health Check
venv\Scripts\python.exe run.py --health

# Runtime Smoke Test
venv\Scripts\python.exe run.py --smoke
```

## Repository Layout

```text
.
├── api/                 # FastAPI app, routers, executor, approvals
├── core/                # Agent runtime, config, CLI/TUI
├── skills/              # Tool implementations and registry
├── frontend/            # React + TypeScript + Electron
├── scripts/             # Build and helper scripts
├── docs/                # Delivery and resume documents
├── run.py               # CLI entry
├── run_api.py           # API entry
├── run_tui.py           # TUI entry
└── API_CONTRACT.md      # Frontend-backend API contract
```

## Documentation

- API Contract: [`API_CONTRACT.md`](./API_CONTRACT.md)
- User Guide (Chinese): [`docs/USER_GUIDE_zh.md`](./docs/USER_GUIDE_zh.md)
- Mentor Delivery Notes: [`docs/MENTOR_DELIVERY.md`](./docs/MENTOR_DELIVERY.md)
- Resume Snippets: [`docs/RESUME_SNIPPETS.md`](./docs/RESUME_SNIPPETS.md)
- Frontend Details: [`frontend/README.md`](./frontend/README.md)

## Validation Status (2026-02-28)

- `run.py --health`: passed, result `基本健康（0 阻断，3 个警告）`
- `frontend npm run build`: sandbox environment may hit `spawn EPERM` (permission-related)

Current warning items from health check:

- Search keys missing: `SERPER_API_KEY` / `BING_API_KEY`
- Optional deps missing: `PyPDF2`, `pptx`
