#!/bin/bash
# NexusAgent 一键启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}      NexusAgent 启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo -e "${RED}错误: 未安装 uv${NC}"
    echo "请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 检查 node_modules
if [ ! -d "frontend/web/node_modules" ]; then
    echo -e "${YELLOW}前端依赖未安装，正在安装...${NC}"
    cd frontend/web && npm install && cd ../..
fi

# 默认端口
BACKEND_PORT="${PORT:-8765}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:${FRONTEND_PORT},http://localhost:5173,http://localhost:3000}"

echo -e "${YELLOW}配置信息:${NC}"
echo "  后端端口: $BACKEND_PORT"
echo "  前端端口: $FRONTEND_PORT"
echo "  CORS来源: $CORS_ORIGINS"
echo ""

# 检查端口是否被占用
check_port() {
    if lsof -i:$1 -sTCP:LISTEN &> /dev/null; then
        echo -e "${RED}错误: 端口 $1 已被占用${NC}"
        echo "  请先关闭占用端口的进程，或设置不同的 PORT/FRONTEND_PORT 环境变量"
        return 1
    fi
    return 0
}

# 检查后端端口
if ! check_port $BACKEND_PORT; then
    exit 1
fi

# 启动后端
echo -e "${YELLOW}启动后端...${NC}"
CORS_ORIGINS="$CORS_ORIGINS" uv run python -m nexus.web.server &
BACKEND_PID=$!
echo -e "${GREEN}后端已启动 (PID: $BACKEND_PID)${NC}"

# 等待后端启动
sleep 2

# 启动前端
echo -e "${YELLOW}启动前端...${NC}"
cd frontend/web
npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}前端已启动 (PID: $FRONTEND_PID)${NC}"

# 保存 PID
echo "$BACKEND_PID $FRONTEND_PID" > .nexus_pids

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}NexusAgent 已成功启动！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  后端: http://localhost:$BACKEND_PORT"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"

# 等待信号
trap "echo -e '${RED}正在停止服务...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; rm -f .nexus_pids; exit" SIGINT SIGTERM

wait
