#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# TASKFORZE — AlloyDB Provisioning + Auth Proxy + Migration Runner
# Run from the TaskForze project root.
# Usage:  DB_PASSWORD=mypassword ./scripts/setup_alloydb.sh
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── CONFIGURATION ──────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-taskforze}"
REGION="${REGION:-asia-south1}"
CLUSTER="${CLUSTER:-taskforze-cluster}"
INSTANCE="${INSTANCE:-taskforze-primary}"
DB_USER="${DB_USER:-taskforze_user}"
DB_NAME="${DB_NAME:-taskforze}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [[ -z "$DB_PASSWORD" ]]; then
    read -rsp "Enter AlloyDB password for ${DB_USER}: " DB_PASSWORD
    echo
fi

# ─── STEP 1: Set project ────────────────────────────────────────────────────
echo "▶ [1/12] Setting project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

# ─── STEP 2: Enable APIs ────────────────────────────────────────────────────
echo "▶ [2/12] Enabling required Google Cloud APIs"
gcloud services enable \
    alloydb.googleapis.com \
    sqladmin.googleapis.com \
    secretmanager.googleapis.com \
    cloudrun.googleapis.com \
    --quiet

# ─── STEP 3: Create AlloyDB cluster ─────────────────────────────────────────
echo "▶ [3/12] Creating AlloyDB cluster: ${CLUSTER}"
gcloud alloydb clusters create "${CLUSTER}" \
    --region="${REGION}" \
    --password="${DB_PASSWORD}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || echo "  ↳ Cluster already exists — skipping"

# ─── STEP 4: Create primary instance ────────────────────────────────────────
echo "▶ [4/12] Creating primary instance: ${INSTANCE}"
gcloud alloydb instances create "${INSTANCE}" \
    --cluster="${CLUSTER}" \
    --region="${REGION}" \
    --instance-type=PRIMARY \
    --cpu-count=2 \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || echo "  ↳ Instance already exists — skipping"

# ─── STEP 5: Get connection name ────────────────────────────────────────────
echo "▶ [5/12] Getting AlloyDB connection details (takes ~2 min first time)"
ALLOYDB_IP=$(gcloud alloydb instances describe "${INSTANCE}" \
    --cluster="${CLUSTER}" --region="${REGION}" --project="${PROJECT_ID}" \
    --format="value(ipAddress)")

CONNECTION_NAME="${PROJECT_ID}/${REGION}/${CLUSTER}/${INSTANCE}"
echo "  Private IP: ${ALLOYDB_IP}"
echo "  Connection: ${CONNECTION_NAME}"

# ─── STEP 6: Install AlloyDB Auth Proxy ─────────────────────────────────────
PROXY_VERSION="1.10.0"
if ! command -v alloydb-auth-proxy &>/dev/null; then
    echo "▶ [6/12] Downloading AlloyDB Auth Proxy v${PROXY_VERSION}"
    curl -fsSL \
        "https://storage.googleapis.com/alloydb-auth-proxy/v${PROXY_VERSION}/alloydb-auth-proxy.linux.amd64" \
        -o /tmp/alloydb-auth-proxy
    chmod +x /tmp/alloydb-auth-proxy
    sudo mv /tmp/alloydb-auth-proxy /usr/local/bin/alloydb-auth-proxy
else
    echo "▶ [6/12] Auth Proxy already installed"
fi

# ─── STEP 7: Start Auth Proxy (background) ──────────────────────────────────
echo "▶ [7/12] Starting AlloyDB Auth Proxy on 127.0.0.1:5432"
alloydb-auth-proxy "${CONNECTION_NAME}" \
    --address "127.0.0.1" --port 5432 &
PROXY_PID=$!
echo "  Auth Proxy PID: ${PROXY_PID}"
sleep 5

# ─── STEP 8: Create DB user + database ──────────────────────────────────────
echo "▶ [8/12] Creating DB user '${DB_USER}' and database '${DB_NAME}'"
PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p 5432 -U postgres <<SQL
DO \$\$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
    END IF;
END \$\$;
SQL

PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p 5432 -U postgres \
    -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
    || PGPASSWORD="${DB_PASSWORD}" createdb \
        -h 127.0.0.1 -p 5432 -U postgres -O "${DB_USER}" "${DB_NAME}"

PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p 5432 -U postgres \
    -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"

# ─── STEP 9: Apply bootstrap schema ─────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "▶ [9/12] Applying AlloyDB bootstrap schema"
PGPASSWORD="${DB_PASSWORD}" psql \
    -h 127.0.0.1 -p 5432 \
    -U "${DB_USER}" -d "${DB_NAME}" \
    -f "${SCRIPT_DIR}/../db/alloydb_bootstrap.sql"
echo "  ✓ Schema applied"

# ─── STEP 10: Update .env ───────────────────────────────────────────────────
echo "▶ [10/12] Updating .env with AlloyDB DATABASE_URL"
ENV_FILE="${SCRIPT_DIR}/../.env"
if grep -q "^DATABASE_URL=" "${ENV_FILE}"; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}|" "${ENV_FILE}"
else
    echo "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}" >> "${ENV_FILE}"
fi
echo "  ✓ .env updated"

# ─── STEP 11: Run Alembic migrations ────────────────────────────────────────
echo "▶ [11/12] Running Alembic migrations"
cd "${SCRIPT_DIR}/.."
.venv/bin/python3 -m alembic upgrade head
echo "  ✓ Migrations complete"

# ─── STEP 12: Verification ──────────────────────────────────────────────────
echo "▶ [12/12] Verifying tables"
PGPASSWORD="${DB_PASSWORD}" psql -h 127.0.0.1 -p 5432 -U "${DB_USER}" -d "${DB_NAME}" \
    -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1;"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo " ✅  AlloyDB setup complete!"
echo "     Cluster:    ${CLUSTER}"
echo "     Instance:   ${INSTANCE}  (${ALLOYDB_IP})"
echo "     Database:   ${DB_NAME}   (user: ${DB_USER})"
echo "     Auth Proxy: PID ${PROXY_PID} → 127.0.0.1:5432"
echo ""
echo "     To stop the proxy:  kill ${PROXY_PID}"
echo "     To start it again:  alloydb-auth-proxy ${CONNECTION_NAME} --port 5432 &"
echo "══════════════════════════════════════════════════════════════"
