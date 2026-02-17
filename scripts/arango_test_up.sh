#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

: "${ARANGO_HOST:=localhost}"
: "${ARANGO_PORT:=18529}"
: "${ARANGO_USERNAME:=root}"
: "${ARANGO_ROOT_PASSWORD:=testpassword123}"
: "${ARANGO_DATABASE:=entity_resolution_test}"

ARANGO_IMAGE="${ARANGO_IMAGE:-arangodb:3.12}"
CONTAINER_NAME="${ARANGO_TEST_CONTAINER_NAME:-arango-entity-resolution-test}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"

if docker ps -a --format '{{.Names}}' | python3 -c "import sys; names=set(sys.stdin.read().split()); sys.exit(0 if '${CONTAINER_NAME}' in names else 1)"; then
  if docker ps --format '{{.Names}}' | python3 -c "import sys; names=set(sys.stdin.read().split()); sys.exit(0 if '${CONTAINER_NAME}' in names else 1)"; then
    echo "ArangoDB test container already running: ${CONTAINER_NAME} (port ${ARANGO_PORT})"
    exit 0
  fi
  echo "Removing existing stopped container: ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

python3 - <<PY
import socket, sys
host="${ARANGO_HOST}"
port=int("${ARANGO_PORT}")
s=socket.socket()
try:
    s.bind((host, port))
except OSError as e:
    print(f"ERROR: {host}:{port} is not available ({e}). Update ARANGO_PORT in .env or stop the conflicting service.", file=sys.stderr)
    sys.exit(2)
finally:
    s.close()
PY

echo "Starting ArangoDB test container: ${CONTAINER_NAME} on ${ARANGO_HOST}:${ARANGO_PORT}"
docker run -d \
  --name "${CONTAINER_NAME}" \
  -e ARANGO_ROOT_PASSWORD="${ARANGO_ROOT_PASSWORD}" \
  -e ARANGO_NO_AUTH=false \
  -p "${ARANGO_PORT}:8529" \
  "${ARANGO_IMAGE}" >/dev/null

echo "Waiting for ArangoDB to become ready..."
ready="false"
for _ in $(seq 1 "${WAIT_SECONDS}"); do
  if curl -u "${ARANGO_USERNAME}:${ARANGO_ROOT_PASSWORD}" -sS "http://${ARANGO_HOST}:${ARANGO_PORT}/_api/version" >/dev/null 2>&1; then
    ready="true"
    break
  fi
  sleep 1
done

if [ "${ready}" != "true" ]; then
  echo "ArangoDB did not become ready within ${WAIT_SECONDS}s" >&2
  docker logs "${CONTAINER_NAME}" >&2 || true
  exit 1
fi

echo "Ensuring database exists: ${ARANGO_DATABASE}"
db_response="$(
  curl -u "${ARANGO_USERNAME}:${ARANGO_ROOT_PASSWORD}" -sS \
    -X POST "http://${ARANGO_HOST}:${ARANGO_PORT}/_api/database" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${ARANGO_DATABASE}\"}"
)"

python3 - <<PY
import json, sys
data=json.loads(r'''${db_response}''')
# If it already exists, Arango returns an error; that's fine for our use.
if data.get("error") is True and data.get("errorNum") not in (1207,):  # 1207: duplicate name
    print("Failed to create database:", data, file=sys.stderr)
    sys.exit(1)
PY

echo "ArangoDB test container is ready."

