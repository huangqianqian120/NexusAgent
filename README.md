# NexusAgent

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

**NexusAgent** 是基于 Claude Code 架构的开源 AI Agent 开发框架，在原版基础上增强了记忆管理、技能系统和 Web 可观测性。

> ⚠️ 本项目基于 [Claude Code](https://github.com/anthropics/claude-code) 和 [OpenHarness](https://github.com/HKUDS/OpenHarness) 构建。

## 核心特性

### 🧠 记忆系统（新增）
- **双层记忆模型** — Header（快速召回）+ Content（完整内容，按需加载）
- **混合召回** — lexical + recency + priority + graph 多维度评分
- **Token 预算控制** — 可配置召回 budget，默认 2000 tokens
- **自动 Consolidation** — 优先级衰减、去重、TTL 归档
- **类型分类** — fact / episode / preference / procedure 四种记忆类型

### ⚡ 技能系统
- **兼容 anthropics/skills** — 生态兼容
- **运行时动态加载** — 可通过 Web UI 上传/编辑/删除
- **技能市场** — 技能注册表管理

### 🔧 工具系统
- **43+ 内置工具** — 文件操作、Shell、搜索、Web、MCP 协议
- **MCP 协议支持** — Model Context Protocol 扩展
- **权限钩子** — PreTool/PostTool 钩子，精细控制

### 🌐 Web UI（新增）
- **实时对话界面** — Socket.IO 双向通信
- **会话管理** — 跨会话恢复、历史记录
- **记忆面板** — 可视化查看/搜索记忆
- **技能面板** — Web UI 管理技能
- **多 Provider 切换** — 一键切换后端模型

### 🤖 多智能体协作
- **Subagent 派生** — 动态创建子 Agent
- **Swarm 团队协作** — CLAUDE_CODE_* 环境变量配置
- **后台任务** — 长时间运行任务管理

## 快速开始

### 方式一：命令行（CLI）

```bash
# 克隆仓库
git clone git@github.com:huangqianqian120/NexusAgent.git
cd NexusAgent

# 安装依赖
uv sync

# 配置环境变量（根据你的 Provider 选择）
export OPENAI_BASE_URL=<your-provider-base-url>   # 例：https://api.openai.com/v1
export ANTHROPIC_API_KEY=<your-api-key>
export OPENAI_MODEL=<your-model>                  # 例：gpt-4o、claude-sonnet-4-20250514

# 交互模式
uv run nexus

# 单次查询
uv run nexus -p "解释这段代码"
```

### 方式二：Web UI

**推荐使用一键启动脚本：**

```bash
# 一键启动（自动检测依赖和端口）
./start.sh

# 一键停止
./stop.sh

# 访问 http://localhost:5173（端口被占用时自动切换）
```

**或手动启动：**

```bash
# 启动后端 API 服务（必须设置 CORS_ORIGINS）
CORS_ORIGINS="http://localhost:5173,http://localhost:5174,http://localhost:3000" uv run python -m nexus.web.server &

# 启动前端（另一个终端）
cd frontend/web
npm run dev

# 访问 http://localhost:5173（端口被占用时自动切换到 5174/5175...）
```

Web UI 功能：
- 实时对话（Socket.IO 双向通信）
- 记忆面板（侧边栏 Brain 按钮）
- 技能面板（侧边栏 Skills 按钮）
- 会话历史（侧边栏 历史会话 按钮）
- 设置面板（Provider/Model 切换）

## 架构

NexusAgent 实现了完整的 Agent Harness 模式：

```
┌─────────────────────────────────────────────────────────┐
│                      Web UI / CLI                      │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Agent Loop                           │
│  ┌─────────┐    ┌──────────┐    ┌───────────────┐   │
│  │ Memory  │ +  │ Skills   │ +  │ Tool Registry │   │
│  │ System  │    │ System   │    │ (43+ tools)   │   │
│  └─────────┘    └──────────┘    └───────────────┘   │
│                           │                           │
│  ┌─────────────────────────────────────────────────┐  │
│  │              API Client (Multi-Provider)         │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

模型负责"思考"，Harness 负责"执行"——安全、高效、可观测。

## 项目结构

```
NexusAgent/
├── src/nexus/              # 核心 Python 包
│   ├── memory/             # 记忆系统（新增双层模型）
│   ├── skills/             # 技能系统
│   ├── tools/              # 工具注册表
│   ├── services/           # 会话、压缩等服务
│   ├── coordinator/        # Agent 协调器
│   ├── swarm/              # 多 Agent 协作
│   └── web/                # Web 服务端（新增）
├── frontend/web/           # React 前端（新增）
│   └── src/
│       ├── components/     # UI 组件
│       ├── hooks/          # WebSocket 等 Hooks
│       └── lib/            # API 客户端
└── scripts/                # 安装脚本
```


## 鸣谢

- **Claude Code** — [Anthropic](https://github.com/anthropics/claude-code) — 原始项目
- **memBook** — [Larkspur-Wang/memBook](https://github.com/Larkspur-Wang/memBook) — 双层记忆模型灵感来源
- **OpenHarness** — [HKUDS](https://github.com/HKUDS/OpenHarness) — 中间层框架
- **nanobot** — [nanobot-ai](https://github.com/nanobot-ai/nanobot) — Channel 实现来源

## License

MIT
