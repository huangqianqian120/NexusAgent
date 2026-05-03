#!/bin/bash
# NexusAgent 停止脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/.nexus_pids"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}正在停止 NexusAgent 服务...${NC}"

stopped_any=false

# 优先使用 PID 文件
if [ -f "$PID_FILE" ]; then
    read -r BACKEND_PID FRONTEND_PID < "$PID_FILE" 2>/dev/null || true

    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null && echo -e "${GREEN}已停止后端 (PID: $BACKEND_PID)${NC}" || true
        stopped_any=true
    fi

    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null && echo -e "${GREEN}已停止前端 (PID: $FRONTEND_PID)${NC}" || true
        stopped_any=true
    fi

    rm -f "$PID_FILE"
fi

# 兜底：精确匹配本项目进程（仅匹配本项目路径下的 vite 和 nexus.web.server）
if [ "$stopped_any" = false ]; then
    # 仅杀死本项目下的 nexus.web.server 进程
    NEXUS_PIDS=$(pgrep -f "nexus\.web\.server" 2>/dev/null || true)
    VITE_PIDS=$(pgrep -f "vite" 2>/dev/null || true)

    local_stopped=false
    for pid in $NEXUS_PIDS; do
        # 检查进程命令行是否包含本项目路径
        if ps -p "$pid" -o command= 2>/dev/null | grep -q "$SCRIPT_DIR"; then
            kill "$pid" 2>/dev/null && echo -e "${GREEN}已停止后端 (PID: $pid)${NC}" || true
            local_stopped=true
        fi
    done

    for pid in $VITE_PIDS; do
        if ps -p "$pid" -o command= 2>/dev/null | grep -q "$SCRIPT_DIR/frontend"; then
            kill "$pid" 2>/dev/null && echo -e "${GREEN}已停止本项目前端 (PID: $pid)${NC}" || true
            local_stopped=true
        fi
    done

    if [ "$local_stopped" = false ]; then
        echo -e "${YELLOW}未发现正在运行的 NexusAgent 进程${NC}"
    fi
fi

echo -e "${GREEN}停止完成${NC}"
