#!/bin/bash
# NexusAgent 停止脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${RED}正在停止 NexusAgent 服务...${NC}"

# 从 PID 文件读取
if [ -f ".nexus_pids" ]; then
    read -r BACKEND_PID FRONTEND_PID < .nexus_pids
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null && echo -e "${GREEN}已停止后端 (PID: $BACKEND_PID)${NC}" || true
    kill $FRONTEND_PID 2>/dev/null && echo -e "${GREEN}已停止前端 (PID: $FRONTEND_PID)${NC}" || true
    rm -f .nexus_pids
else
    # 尝试自动查找并停止
    pkill -f "nexus.web.server" && echo -e "${GREEN}已停止后端${NC}" || true
    pkill -f "vite" && echo -e "${GREEN}已停止前端${NC}" || true
fi

echo -e "${GREEN}停止完成${NC}"
