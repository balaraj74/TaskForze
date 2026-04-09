#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# start_proxy.sh — Start AlloyDB Auth Proxy on localhost:5432
# Run this before starting TaskForze backend in dev / Cloud Run sidecar setup.
# Usage:  ./scripts/start_proxy.sh
# ────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-taskforze}"
REGION="${REGION:-asia-south1}"
CLUSTER="${CLUSTER:-taskforze-cluster}"
INSTANCE="${INSTANCE:-taskforze-primary}"

CONNECTION_NAME="${PROJECT_ID}/${REGION}/${CLUSTER}/${INSTANCE}"
PIDFILE="/tmp/alloydb-proxy.pid"

if [[ -f "${PIDFILE}" ]]; then
    PID=$(cat "${PIDFILE}")
    if kill -0 "${PID}" 2>/dev/null; then
        echo "✅ AlloyDB Auth Proxy already running (PID ${PID})"
        exit 0
    fi
fi

echo "▶ Starting AlloyDB Auth Proxy → 127.0.0.1:5432"
echo "  Connection: ${CONNECTION_NAME}"

alloydb-auth-proxy "${CONNECTION_NAME}" \
    --address 127.0.0.1 \
    --port 5432 \
    --structured-logs &

PROXY_PID=$!
echo "${PROXY_PID}" > "${PIDFILE}"
sleep 3

if kill -0 "${PROXY_PID}" 2>/dev/null; then
    echo "✅ Proxy started (PID ${PROXY_PID}). To stop: kill ${PROXY_PID}"
else
    echo "❌ Proxy failed to start. Check gcloud auth and connection name."
    exit 1
fi
