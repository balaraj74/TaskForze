#!/bin/bash

# Terminal Colors
CYAN='\033[1;36m'
MAGENTA='\033[1;35m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
RED='\033[1;31m'
NC='\033[0m' # No Color

clear
echo -e "${CYAN}"
cat << "EOF"
 ______    _      ____   __ __  ____     ___    ___   _____   _____
/_  __/   / \    / __/  | |/ / |  ___|  / _ \  | _ \ |__  /  | ___|
 / /     / _ \   _\ \   | ' <  |  __|  | (_) | |   /   / /   | __|
/_/     /_/ \_\  \___/  |_|\_\ |_|      \___/  |_|_\  /___|  |____|
EOF
echo -e "${MAGENTA}                 AI Operations Center${NC}"
echo -e ""
echo -e "${YELLOW}🚀 Booting up the Nexus environment...${NC}\n"

# Trap Ctrl+C (SIGINT) and kill all child processes cleanly
trap "echo -e '\n${RED}🛑 Stopping all servers...${NC}'; kill 0" SIGINT SIGTERM EXIT

echo -e "${BLUE}🐍 Starting FastAPI backend on http://localhost:8000...${NC}"
# Start the backend in the background
source .venv/bin/activate && uvicorn nexus.main:app --reload --port 8000 &

echo -e "${GREEN}⚛️ Starting Next.js frontend on http://localhost:3000...${NC}"
# Start the frontend in the background
cd frontend && npm run dev &

echo ""
echo -e "${CYAN}✅ Both servers are actively running in the background!${NC}"
echo -e "   - Frontend: ${MAGENTA}http://localhost:3000${NC}"
echo -e "   - Backend:  ${MAGENTA}http://localhost:8000${NC}"
echo -e "\n   ${YELLOW}Press Ctrl+C to safely shut down both nodes.${NC}"
echo -e "${CYAN}======================================================${NC}"

# Wait for background processes so the script doesn't exit immediately
wait
