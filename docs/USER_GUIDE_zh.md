# AI 个人助手 — 用户手册

## 1. 启动方式

### 1 分钟快速启动（推荐）

```bash
# 终端 1（项目根目录）
.\start_api.cmd

# 终端 2（项目根目录）
.\start_frontend.cmd
```

启动后：
1. 打开浏览器访问 `http://127.0.0.1:5173`
2. 默认进入 Chat 页面
3. 如果后端未起来，先检查终端 1 是否有报错

### 启动前准备（Windows）

```bash
# 在项目根目录执行一次
venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm.cmd install
```

如果你使用 PyCharm，请确认 Project Interpreter 指向项目内 `venv`。
如果你在 PowerShell 里运行命令，统一使用 `npm.cmd`，不要直接写 `npm`。

### CLI 模式（终端对话）

```bash
venv\Scripts\python.exe run.py
```

启动后直接在终端输入自然语言与 AI 对话。AI 会自动判断是否需要调用工具。输入 `exit` 或 `quit` 退出，对话自动保存，下次启动可恢复。

```bash
# 健康检查（验证配置和依赖是否正常）
venv\Scripts\python.exe run.py --health

# 冒烟测试（端到端验收）
venv\Scripts\python.exe run.py --smoke
```

### Web 模式（前端 + API）

```bash
# 终端 1：启动后端 API
venv\Scripts\python.exe run_api.py --port 8000
# 或直接使用
.\start_api.cmd

# 终端 2：启动前端开发服务器
cd frontend && npm.cmd run dev
# 或直接使用
.\start_frontend.cmd
```

浏览器打开后默认进入 Chat 页面。侧边栏可切换到各功能模块。

### 常见启动顺序（建议）

1. 先起后端（`run_api.py` / `start_api.cmd`）
2. 再起前端（`npm.cmd run dev` / `start_frontend.cmd`）
3. 打开 Chat 页面，先发一句 “你好” 验证链路
4. 再进 System 页面点一次 `Refresh Health`

---

## 2. 核心功能与示例提示词

### 2.1 自然语言对话（Chat）

直接用中文描述你的需求，AI 会自动选择合适的工具执行。

| 你说的话 | AI 会做什么 |
|---------|-----------|
| "帮我看看当前目录有什么文件" | 调用 `list_dir` |
| "读一下 test/test1.py 的内容" | 调用 `read_file` |
| "把第 5 行的 print 改成 logging.info" | 调用 `edit_file` |
| "运行 git status" | 调用 `run_command`（需审批） |
| "帮我写一个快速排序放到 test/sort.py" | 调用 `write_code_file`（需审批） |

Chat 页面交互增强（Web）：

1. 输入框支持 `Enter` 发送，`Shift+Enter` 换行。
2. 输入 `/` 可触发内置命令建议（如 `/clear`、`/new`、`/stop`、`/attach`）。
3. 支持附件：点击回形针或直接拖拽文件到聊天区。
4. 每条消息悬停可见操作按钮（`Copy`、`Edit`、`Retry`）。
5. 消息头显示时间戳，便于定位执行顺序。

### 2.2 待办事项

```
帮我添加一个待办：周五前提交论文初稿，优先级高，分类学习
列出我的待办
把 #3 标记为完成
删除 #5
清除所有已完成的待办
```

### 2.3 笔记管理

```
创建一个笔记，标题"会议记录"，内容是今天讨论了项目进度
在"会议记录"笔记后面追加：决定下周三前完成原型
搜索笔记中包含"项目"的内容
列出所有笔记
```

### 2.4 提醒

```
提醒我 2026-03-01 09:00 交奖学金申请表
列出所有提醒
检查有没有到期的提醒
```

### 2.5 记忆系统

```
记住：我喜欢简洁的中文回复，不要太啰嗦
（→ 写入全局记忆，每次对话自动生效）

记住关于 project_alpha 的信息：使用 React + FastAPI 架构，部署在 AWS
（→ 写入话题记忆，需要时手动调用）

回忆一下 project_alpha 的信息
列出所有记忆话题
```

### 2.6 任务规划

```
帮我规划一下申请研究生的流程
（AI 会调用 create_plan 列出步骤，然后逐步执行，每完成一步自动 update_plan）
```

### 2.7 文件操作

```
把桌面上所有 .pdf 文件移动到 documents 文件夹
在 config.py 的第 10 行后面插入一行 import os
删除 test.py 的第 20-25 行
搜索项目里所有包含 TODO 的文件
```

### 2.8 知识库（RAG）

```
把 data/knowledge_base 下的文档建立索引
从知识库中搜索"申请截止日期"
```

向量记忆：
```
把这段长文本存入向量记忆，标签是 study,math
语义搜索：我之前关于线性代数的笔记
查看向量记忆状态
```

### 2.9 留学申请管理

```
添加 CMU MSCS 到选校列表，2026 Fall 入学，截止日期 2025-12-15
列出所有选校
对比 CMU 和 Stanford 的 CS 项目
生成申请时间线，目标 2026 Fall 入学
```

### 2.10 学习助手

```
帮我制定 GRE 备考计划，目标 verbal 160+，还有 30 天，每天 3 小时
生成线性代数期末考试复习包
用通俗的方式解释反向传播算法
```

### 2.11 学术写作

```
帮我写一份 CS 硕士申请的 SOP 初稿，语气专业简洁
修改这段文字：[粘贴草稿]，要求更正式、结构更清晰
```

### 2.12 通知与定时任务

```
发一条通知到 console 渠道，内容是"测试通知"
创建一个定时任务：每天早上 8 点推送待办摘要
列出所有定时任务
查看调度器执行日志
```

### 2.13 审计与诊断

```
看看今天调用了哪些工具
统计一下工具使用情况
只看失败的调用记录
```

---

## 3. 审批机制

涉及文件修改、命令执行等高风险操作时，系统会拦截并请求审批。

### CLI 模式

弹出审批面板后可选择：

| 按键 | 操作 |
|------|------|
| `y` | 批准执行 |
| `n` | 拒绝 |
| `v` | 查看详情（diff / 完整参数） |
| `r` | 拒绝并给出修改意见，AI 会重试 |
| `m` | 手动修改参数后执行 |

### Web 模式

右侧弹出 Approval Drawer，显示 dry-run 预览，点击 Confirm Execute 确认。

### 高风险工具列表

以下工具触发审批（可在 `core/config.py` 的 `RISKY_TOOLS` 中增减）：

`write_code_file` `edit_file` `insert_text` `delete_lines` `multi_edit` `create_file` `rename_file` `delete_file` `move_file_by_ext` `run_command` `save_memory` `undo_edit` `video_clip` `notify_manage` `grad_school_manage` `grad_school_research` `reminder_push` `runtime_smoke` `skill_scaffold_create`

---

## 4. 添加新技能

### 方式一：简易注册（推荐）

在 `skills/` 目录下新建 `.py` 文件，使用 `register_simple` 装饰器：

```python
# skills/my_custom_tools.py
from .registry import register_simple

@register_simple({
    "name": "my_tool",
    "description": "我的自定义工具，做某件事",
    "args": {
        # 简写：值为字符串 → 默认 string 类型，required
        "query": "搜索关键词",

        # 详写：值为 dict → 可指定类型、是否必填、默认值
        "top_k": {
            "desc": "返回数量",
            "type": "integer",    # 支持: string/integer/number/boolean/array/object
            "default": 5          # 提供 default 自动变为可选参数
        },
        "verbose": {
            "desc": "是否详细输出",
            "type": "boolean",
            "required": False     # 显式标记为可选
        },
    }
})
def my_tool(query: str, top_k: int = 5, verbose: bool = False):
    result = f"搜索 {query}，返回 {top_k} 条结果"
    if verbose:
        result += "\n（详细模式）"
    return result
```

保存后重启进程即可，系统自动发现并加载，无需修改任何其他文件。

### 方式二：原生注册（精细控制）

适合需要精确控制 JSON Schema 的场景：

```python
# skills/advanced_tools.py
from .registry import register

my_schema = {
    "type": "function",
    "function": {
        "name": "advanced_tool",
        "description": "高级工具示例",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "delete"],
                    "description": "操作类型"
                },
                "data": {
                    "type": "object",
                    "description": "操作数据"
                }
            },
            "required": ["action"]
        }
    }
}

@register(my_schema)
def advanced_tool(action: str, data: dict = None):
    return f"执行 {action}，数据: {data}"
```

### 方式三：Skill Studio（Web UI 可视化创建）

1. 打开前端，侧边栏进入 Skill Studio
2. 填写 Module Name、Tool Name、Description
3. 在 Params JSON 中定义参数（格式见下方）
4. 可选开启 AI Completion 让后端自动生成函数体
5. 点击 Preview 预览代码，确认后点击 Create 生成文件

参数 JSON 格式：
```json
[
  {"name": "query", "type": "string", "description": "搜索文本", "required": true},
  {"name": "top_k", "type": "integer", "description": "最大结果数", "required": false, "default": 5}
]
```

---

## 5. Web 前端快捷键

| 快捷键 | 功能 |
|--------|------|
| `/` 或 `Ctrl/Cmd + K` | 打开 Command Palette，快速跳转页面 |
| `Ctrl/Cmd + L` | 清空当前聊天 |
| `Ctrl/Cmd + N` | 新建聊天 |
| `?` | 打开快捷键帮助面板 |
| `Enter` | Chat 页面发送消息 |
| `Shift+Enter` | Chat 页面换行 |
| `Esc` | 关闭 Command Palette / 中断当前运行 |
| `↑` `↓` | Command Palette 中导航 |

### 5.1 Command Palette 使用说明

1. 支持模糊搜索（不要求完整匹配）。
2. 结果按“近期使用频率 + 最近使用时间”排序（frecency）。
3. 每个命令项显示图标与快捷键提示。

### 5.2 主题与动效切换

Header 顶部有两个下拉框：
1. `Theme`：切换颜色主题（带色块预览）。
2. `Motion`：切换动效模式（`Full` / `Perf` / `Reduced`）。

当系统开启减少动态效果（`prefers-reduced-motion`）时，界面会自动降级动画。

---

## 6. 项目结构

```
ai-agent/
├── run.py              # CLI 入口
├── run_api.py          # Web API 入口
├── core/
│   ├── config.py       # 配置（API Key、模型、高风险工具列表）
│   ├── client.py       # OpenAI 客户端初始化
│   ├── engine.py       # CLI 对话引擎（Agent Loop）
│   └── ui.py           # CLI 界面（Rich 美化）
├── skills/             # 所有技能模块（自动发现加载）
│   ├── registry.py     # 技能注册器（register / register_simple）
│   ├── path_safety.py  # 路径安全沙箱
│   ├── file_tools.py   # 文件操作
│   ├── edit_tools.py   # 精确编辑（find & replace）
│   ├── shell_tools.py  # 命令执行（带安全拦截）
│   ├── daily_tools.py  # 待办/笔记/提醒
│   ├── memory_tools.py # 记忆系统
│   ├── plan_tools.py   # 任务规划（持久化）
│   ├── rag_tools.py    # 向量记忆（ChromaDB）
│   ├── audit_tools.py  # 审计日志
│   └── ...             # 更多技能模块
├── api/
│   ├── app.py          # FastAPI 应用
│   ├── executor.py     # 工具执行器（含审批流程）
│   └── routers/        # API 路由（chat/system/tools/...）
├── frontend/           # React + TypeScript + Ant Design
│   └── src/
│       ├── pages/      # ChatPage / SystemDashboard / ModuleWorkbench
│       ├── components/ # ToolForm / ApprovalDrawer / CommandPalette / ...
│       └── modules/    # 前端模块注册表
├── data/               # 持久化数据（待办、提醒、计划等）
├── memories/           # 记忆存储（全局/话题/对话历史）
└── .env                # 环境变量（KIMI_API_KEY）
```

---

## 7. 配置

### 环境变量（.env）

```env
KIMI_API_KEY=你的API密钥
```

### 模型配置（core/config.py）

```python
API_KEY = os.getenv("KIMI_API_KEY")
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_NAME = "moonshot-v1-32k"
```

如需切换模型，修改 `BASE_URL` 和 `MODEL_NAME` 即可。支持任何 OpenAI 兼容 API。

### 调整审批范围

编辑 `core/config.py` 中的 `RISKY_TOOLS` 集合，添加或移除工具名即可。

---

## 8. 常见启动问题排查

### 8.1 终端启动后端提示找不到 API/uvicorn

现象示例：`❌ 缺少 uvicorn`、前端请求 API 失败。  
根因通常是当前终端使用了系统 Python，而不是项目 `venv`。

排查命令：

```bash
python -c "import sys; print(sys.executable)"
```

修复方式：

```bash
venv\Scripts\python.exe run_api.py --port 8000
```

`run_api.py` 已内置自动回退逻辑：如果当前解释器缺依赖，会自动尝试切换到项目 `venv` 重启。

### 8.2 PyCharm 终端无法启动前端

现象示例：`npm : ... cannot be loaded because running scripts is disabled`。  
这是 PowerShell 执行策略拦截了 `npm.ps1`。

可选修复：

1. 在终端改用 `npm.cmd install` / `npm.cmd run dev`（推荐）
2. 直接执行 `.\start_frontend.cmd`
3. 在 PyCharm 设置 Terminal Shell Path 为 `cmd.exe`
4. 临时改用 `cmd /c npm install`、`cmd /c npm run dev`

### 8.3 `npm.cmd install` 仍然报 EPERM

现象示例：`npm ERR! code EPERM`、`operation not permitted`。  
通常是 `node_modules` 被占用，或 npm 缓存目录权限受限。

按顺序执行：

```bash
# 1) 先关闭可能占用依赖目录的进程
taskkill /F /IM node.exe
taskkill /F /IM electron.exe

# 2) 回到前端目录，用项目内缓存安装（避开全局缓存权限问题）
cd frontend
npm.cmd install --cache .npm-cache
```

如果仍失败，请关闭杀毒软件的“实时防护”后重试，或右键用“管理员身份”打开终端再执行一次。

### 8.4 前端页面打不开

按下面顺序检查：

1. 后端是否已启动：访问 `http://127.0.0.1:8000/docs`，能打开说明 API 正常。
2. 前端是否已启动：终端里应出现 Vite 地址 `http://127.0.0.1:5173`。
3. 浏览器地址是否正确：只打开 `http://127.0.0.1:5173`（不要写成 `8000`）。
4. 若 5173 被占用，前端会自动换端口（如 5174）；请打开终端显示的新地址。

### 8.5 `npm.cmd run dev` 报 `Error: spawn EPERM`

这是系统拦截了 Node 子进程（常见于安全软件、权限不足或被占用）。

```bash
cd frontend

# 1) 关闭占用进程
taskkill /F /IM node.exe
taskkill /F /IM electron.exe

# 2) 解锁 esbuild 可执行文件（PowerShell）
powershell -Command "Unblock-File .\node_modules\@esbuild\win32-x64\esbuild.exe"

# 3) 重新启动
npm.cmd run dev
```

如果仍报错，请使用“管理员身份”打开 `cmd.exe` 后再执行 `npm.cmd run dev`。
