# <img src="assets/logo.png" alt="NexusAgent" width="40" style="vertical-align: middle;"> NexusAgent 中文说明

<p align="center">
  <a href="README.md"><strong>English</strong></a> ·
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

**NexusAgent** 是一个基于 Claude Code 架构的开源 AI Agent 开发框架，在原版基础上增强了记忆管理、技能系统和 Web 可观测性。

核心特性：

- 🧠 双层记忆系统（Header + Content 混合召回）
- ⚡ 技能系统（.md 格式，动态加载）
- 🌐 Web UI（实时对话、记忆面板、技能管理）
- 🤖 多 Agent 协作（Subagent + Swarm）
- 🔧 43+ 内置工具 / MCP 协议支持

---

## 快速开始

### 方式一：命令行（CLI）

```bash
# 克隆仓库
git clone https://github.com/huangqianqian120/NexusAgent.git
cd NexusAgent

# 安装依赖
uv sync

# 配置环境变量
export ANTHROPIC_API_KEY=<your-api-key>

# 交互模式
uv run nexus

# 单次查询
uv run nexus -p "解释这段代码"
```

### 方式二：Web UI

```bash
# 启动后端 API 服务
uv run python -m nexus.web.server &

# 启动前端（另一个终端）
cd frontend/web
npm install
npm run dev

# 访问 http://localhost:5173
```

---

## 配置模型与 Provider

### 支持的 LLM Provider

| Provider | Base URL | 示例模型 |
|----------|----------|----------|
| **MiniMax** | `https://api.minimax.chat/v1` | MiniMax-Text-01 |
| **OpenAI** | `https://api.openai.com/v1` | GPT-4o, GPT-4.1 |
| **Anthropic** | `https://api.anthropic.com` | Claude Sonnet 4, Claude Opus 4 |
| **Kimi** | `https://api.moonshot.cn/anthropic` | kimi-k2.5 |
| **Zhipu** | `https://open.bigmodel.cn/api/paas/v4` | glm-4 |
| **DeepSeek** | `https://api.deepseek.com` | deepseek-chat |
| **OpenRouter** | `https://openrouter.ai/api/v1` | 多种开源模型 |
| **Ollama** | `http://localhost:11434/v1` | 本地模型 |

### 环境变量配置

```bash
# 通用配置
export ANTHROPIC_API_KEY=<your-api-key>

# 可选：指定模型
export OPENAI_MODEL=gpt-4o

# 可选：指定 Base URL（使用第三方兼容接口时）
export OPENAI_BASE_URL=<your-provider-base-url>
```

---

## 核心能力

### 🧠 双层记忆系统

- **Header（快速召回）** + **Content（完整内容，按需加载）**
- **混合召回** — lexical + recency + priority + graph 多维度评分
- **Token 预算控制** — 可配置召回 budget，默认 2000 tokens
- **自动 Consolidation** — 优先级衰减、去重、TTL 归档
- **类型分类** — fact / episode / preference / procedure 四种记忆类型

### ⚡ 技能系统

- **.md 格式技能文件** — 易于编写和维护
- **兼容 anthropics/skills** — 生态兼容
- **运行时动态加载** — 可通过 Web UI 上传/编辑/删除
- **技能市场** — 技能注册表管理

### 🌐 Web UI

- **实时对话界面** — Socket.IO 双向通信
- **会话管理** — 跨会话恢复、历史记录
- **记忆面板** — 可视化查看/搜索记忆
- **技能面板** — Web UI 管理技能
- **多 Provider 切换** — 一键切换后端模型

### 🤖 多 Agent 协作

- **Subagent 派生** — 动态创建子 Agent
- **Swarm 团队协作** — CLAUDE_CODE_* 环境变量配置
- **后台任务** — 长时间运行任务管理

### 🔧 工具系统

- **43+ 内置工具** — 文件操作、Shell、搜索、Web、MCP 协议
- **MCP 协议支持** — Model Context Protocol 扩展
- **权限钩子** — PreTool/PostTool 钩子，精细控制

---

## 项目结构

```
NexusAgent/
├── src/nexus/              # 核心 Python 包
│   ├── memory/             # 记忆系统（双层模型）
│   ├── skills/             # 技能系统
│   ├── tools/              # 工具注册表（43+ 工具）
│   ├── services/           # 会话、压缩等服务
│   ├── coordinator/        # Agent 协调器
│   ├── swarm/              # 多 Agent 协作
│   └── web/                # Web 服务端
├── frontend/web/           # React 前端
│   └── src/
│       ├── components/     # UI 组件
│       ├── hooks/          # WebSocket 等 Hooks
│       └── lib/            # API 客户端
└── scripts/                # 安装脚本
```

---

## 与 Claude Code 的差异

| 特性 | Claude Code | NexusAgent |
|------|-------------|------------|
| 界面 | 仅 CLI | CLI + Web UI |
| 记忆 | 基础上下文 | 双层混合召回 + Token 预算 |
| 技能 | 静态加载 | 动态管理 UI |
| 协作 | 单 Agent | 多 Agent Swarm |
| 观测性 | 终端输出 | Web 实时面板 |

---

## 测试

```bash
uv run pytest -q
```

---

## 致谢

NexusAgent 的诞生离不开以下开源项目的启发：

- **Claude Code** — [Anthropic/claude-code](https://github.com/anthropics/claude-code) — 核心架构来源
- **memBook** — [Larkspur-Wang/memBook](https://github.com/Larkspur-Wang/memBook) — 双层记忆模型灵感来源
- **OpenHarness** — [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) — 中间层框架
- **nanobot** — [nanobot-ai/nanobot](https://github.com/nanobot-ai/nanobot) — Channel 实现参考

---

## License

MIT，见 [LICENSE](LICENSE)。

---

**开源地址**: https://github.com/huangqianqian120/NexusAgent

欢迎 Star 和贡献！
