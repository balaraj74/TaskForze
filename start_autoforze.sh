#!/bin/bash
echo "Starting NEXUS FastAPI backend on port 8000..."
cd /home/balaraj/google\ apac/NEXUS/TaskForze
python3 -m uvicorn nexus.main:app --reload --port 8000 &
FASTAPI_PID=$!

echo "Starting AutoForze Go backend..."
cd autoforze
go run ./cmd/autoforze/main.go &
AUTOFORZE_PID=$!

echo "Both services started. Press Ctrl+C to stop."

trap "kill $FASTAPI_PID $AUTOFORZE_PID" SIGINT SIGTERM
wait $FASTAPI_PID $AUTOFORZE_PID
