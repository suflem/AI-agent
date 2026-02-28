# 导师交付说明（AI Agent 项目）

## 1. 交付目标

本项目交付一个可运行、可扩展、可演示的模块化 AI Agent 平台，覆盖：

- Agent 运行时与工具调用
- 模块化后端 API
- 风险工具审批机制
- 前端交互控制台（可扩展为 Electron 桌面端）

## 2. 运行环境

- OS：Windows 10/11（当前仓库默认脚本为 Windows 友好）
- Python：3.10+（当前环境验证为 3.12）
- Node.js：18+（前端）
- 依赖安装：
  - 后端：`venv\Scripts\python.exe -m pip install -r requirements.txt`
  - 前端：`cd frontend && npm.cmd install`

## 3. 启动与演示步骤

### 3.1 后端启动

```bash
venv\Scripts\python.exe run_api.py --host 127.0.0.1 --port 8000
```

检查地址：

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

### 3.2 前端启动

```bash
cd frontend
npm.cmd run dev
```

默认访问：`http://127.0.0.1:5173`

### 3.3 建议演示脚本（8-10 分钟）

1. 展示 `/docs`，说明模块化 API 分层（system/tool/study/kb 等）。  
2. 执行 `GET /api/tool/list`，展示工具规模与统一网关。  
3. 演示一个普通模块调用（如 study/academic 任一）。  
4. 演示高风险工具审批（先 dry-run，再 confirm），说明安全机制。  
5. 展示前端 Module Workbench 与审批抽屉，说明前后端联动。  
6. 执行 `run.py --health`，说明可运维与可验收能力。

## 4. 验收清单（建议）

- [ ] 能启动 API 服务并访问 `/docs`  
- [ ] 能通过 `/api/tool/list` 获取工具列表  
- [ ] 至少一个业务模块接口调用成功  
- [ ] 高风险工具具备审批拦截与确认机制  
- [ ] 前端可连接后端并完成一次操作闭环  
- [ ] `run.py --health` 输出无阻断错误

## 5. 当前验证结果（2026-02-28）

- 健康检查：通过（0 阻断，3 警告）
- 关键能力：工具注册、模块 API、审批流均可工作
- 警告项：
  - 搜索 API Key 未配置（SERPER/BING）
  - 可选依赖缺失（PyPDF2、pptx）

## 6. 已知风险与改进计划

1. 前端构建在受限环境可能出现 `esbuild spawn EPERM`，需按前端 README 的权限修复步骤处理。  
2. 增加自动化测试（当前仓库未安装 `pytest`）以提升回归保障。  
3. 增加 Docker Compose 一键启动，降低跨环境部署成本。  
4. 增加日志追踪与指标面板（成功率、延迟、审批次数）用于长期维护。

