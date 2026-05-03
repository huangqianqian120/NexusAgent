#!/bin/bash
# NexusAgent 一键启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PID_FILE="$SCRIPT_DIR/.nexus_pids"
BACKEND_PORT="${PORT:-8765}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:${FRONTEND_PORT},http://localhost:5173,http://localhost:3000}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-30}"
DAEMON_MODE=false

usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -d, --daemon     后台模式运行"
    echo "  -h, --help       显示帮助"
    echo ""
    echo "环境变量:"
    echo "  PORT             后端端口 (默认: 8765)"
    echo "  FRONTEND_PORT    前端端口 (默认: 5173)"
    echo "  HEALTH_CHECK_TIMEOUT  健康检查超时秒数 (默认: 30)"
    exit 0
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--daemon) DAEMON_MODE=true; shift ;;
        -h|--help) usage ;;
        *) echo -e "${RED}未知参数: $1${NC}"; usage ;;
    esac
done

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

echo -e "${YELLOW}配置信息:${NC}"
echo "  后端端口: $BACKEND_PORT"
echo "  前端端口: $FRONTEND_PORT"

# 检查端口是否已被监听（兼容无 lsof 的系统）
_is_port_in_use() {
    if command -v lsof &> /dev/null; then
        lsof -i:$1 -sTCP:LISTEN &> /dev/null && return 0
    elif command -v python3 &> /dev/null; then
        python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', $1))
    s.close()
    exit(0)
except (OSError, ConnectionRefusedError):
    exit(1)
" 2>/dev/null
    fi
    return 1
}

# 确保端口未被占用，否则报错退出
require_free_port() {
    local port=$1
    local name=$2
    if _is_port_in_use $port; then
        echo -e "${RED}错误: $name 端口 $port 已被占用${NC}"
        echo "  请先关闭占用端口的进程，或设置不同的 ${name}_PORT 环境变量"
        return 1
    fi
    return 0
}

# 健康检查：轮询直到后端端口可连接
wait_for_backend() {
    local port=$1
    local timeout=$2
    local elapsed=0
    echo -n "  等待后端启动"
    while [ $elapsed -lt $timeout ]; do
        if _is_port_in_use $port; then
            echo -e " ${GREEN}就绪${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        elapsed=$((elapsed + 1))
    done
    echo -e " ${RED}超时${NC}"
    return 1
}

# 清理函数
cleanup() {
    echo -e "${RED}正在停止服务...${NC}"
    if [ -f "$PID_FILE" ]; then
        read -r BPID FPID < "$PID_FILE" 2>/dev/null
        [ -n "$BPID" ] && kill "$BPID" 2>/dev/null
        [ -n "$FPID" ] && kill "$FPID" 2>/dev/null
        rm -f "$PID_FILE"
    fi
}

# 检查端口
if ! require_free_port $BACKEND_PORT "BACKEND"; then
    exit 1
fi

# 如果前端端口被占用，自动尝试下一个端口
while ! require_free_port $FRONTEND_PORT "FRONTEND" 2>/dev/null; do
    echo -e "${YELLOW}端口 $FRONTEND_PORT 已被占用，尝试 $((FRONTEND_PORT + 1))${NC}"
    FRONTEND_PORT=$((FRONTEND_PORT + 1))
    [ $FRONTEND_PORT -gt 5180 ] && { echo -e "${RED}无法找到可用前端端口 (5173-5180)${NC}"; exit 1; }
done

# 启动后端
echo -e "${YELLOW}启动后端...${NC}"
CORS_ORIGINS="$CORS_ORIGINS" uv run python -m nexus.web.server &
BACKEND_PID=$!
echo -e "${GREEN}后端 PID: $BACKEND_PID${NC}"

# 健康检查等待后端就绪
if ! wait_for_backend $BACKEND_PORT $HEALTH_CHECK_TIMEOUT; then
    echo -e "${RED}后端启动超时，终止${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# 启动前端
echo -e "${YELLOW}启动前端...${NC}"
cd frontend/web
VITE_PORT=$FRONTEND_PORT npm run dev -- --port $FRONTEND_PORT &
FRONTEND_PID=$!
cd ../..
echo -e "${GREEN}前端 PID: $FRONTEND_PID${NC}"

# 保存 PID
echo "$BACKEND_PID $FRONTEND_PID" > "$PID_FILE"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}NexusAgent 已成功启动！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  后端: http://localhost:$BACKEND_PORT"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo ""

if [ "$DAEMON_MODE" = true ]; then
    echo -e "${YELLOW}后台模式运行中。使用 ./stop.sh 或 kill $BACKEND_PID $FRONTEND_PID 停止${NC}"
    # 脱离终端
    disown $BACKEND_PID 2>/dev/null
    disown $FRONTEND_PID 2>/dev/null
    exit 0
fi

echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
trap cleanup SIGINT SIGTERM

wait
