# Nexus Agent

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

**Nexus** 是新一代企业级 AI Agent 开发框架，提供完整的 Agent 基础设施：工具调用、技能系统、记忆管理和多智能体协作。

## 核心特性

- **Agent Loop** — 流式工具调用循环，指数退避重试，并行执行，Token 计数
- **工具系统** — 43+ 内置工具（文件、Shell、搜索、Web、MCP）
- **技能系统** — 按需加载 .md 格式技能文件，兼容 anthropics/skills
- **记忆系统** — CLAUDE.md 上下文注入，上下文压缩，跨会话持久化
- **权限管理** — 多级权限模式，路径/命令规则，PreTool/PostTool 钩子
- **多智能体** — Subagent 派生，团队协作，后台任务生命周期

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/huangqianqian120/NexusAgent.git
cd NexusAgent

# 安装依赖
uv sync --extra dev

# 运行
uv run nexus -p "你好"
```

### 配置 LLM Provider

```bash
# 交互式配置（推荐）
uv run nexus setup

# 或手动设置环境变量
export OPENAI_BASE_URL=https://api.minimax.chat/v1
export ANTHROPIC_API_KEY=your_api_key
export OPENAI_MODEL=MiniMax-Text-01
```

## 支持的 LLM Provider

| Provider | Base URL | 示例模型 |
|----------|----------|----------|
| **MiniMax** | `https://api.minimax.chat/v1` | MiniMax-Text-01 |
| **OpenAI** | `https://api.openai.com/v1` | GPT-4o, GPT-4.1 |
| **Anthropic** | `https://api.anthropic.com` | Claude Sonnet 4, Claude Opus 4 |
| **Kimi** | `https://api.moonshot.cn/anthropic` | kimi-k2.5 |
| **Zhipu** | 自定义兼容端点 | glm-4.5 |
| **DeepSeek** | `https://api.deepseek.com` | deepseek-chat, deepseek-reasoner |
| **OpenRouter** | `https://openrouter.ai/api/v1` | 多种开源模型 |
| **Ollama** | `http://localhost:11434/v1` | 本地模型 |

## 命令行用法

```bash
# 交互模式
uv run nexus

# 单次查询
uv run nexus -p "解释这段代码"

# JSON 输出（程序化使用）
uv run nexus -p "列出所有函数" --output-format json

# 流式输出
uv run nexus -p "修复这个 bug" --output-format stream-json
```

## 架构

Nexus 实现了完整的 Agent Harness 模式：

```
Agent Loop → API Client → Tool Registry → Permissions/Hooks → 执行
     ↑                                                          |
     └────────────────────── 结果反馈 ──────────────────────────┘
```

模型负责"思考"，Harness 负责"执行"——安全、高效、可观测。

## 企业级特性

- **多租户支持** — 独立的配置和凭证管理
- **权限治理** — 细粒度的操作权限控制
- **审计日志** — 完整的操作记录
- **插件系统** — 扩展能力，兼容 claude-code plugins

## License

MIT
