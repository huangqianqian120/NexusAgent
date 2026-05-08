# ===== NexusAgent Docker 镜像 =====
# 构建: docker build -t nexus-agent .
# 运行: docker run -p 8765:8765 -e SECRET_KEY=xxx -e MULTI_USER_SECRET_KEY=xxx nexus-agent

# 阶段 1: 前端构建
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend/web
COPY frontend/web/package*.json ./
RUN npm ci --production=false
COPY frontend/web/ ./
RUN npm run build

# 阶段 2: 生产运行
FROM python:3.12-slim
WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 复制 Python 项目文件
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY personal_agent/ ./personal_agent/

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/web/dist/ ./frontend/web/dist/

# 安装依赖（含 web + multi-user 可选依赖）
RUN uv sync --extra web --extra multi-user --no-dev

ENV PORT=8765
ENV NEXUS_PRODUCTION=true
EXPOSE 8765

# 启动生产服务器
CMD ["uv", "run", "python", "-m", "nexus.web.server"]
