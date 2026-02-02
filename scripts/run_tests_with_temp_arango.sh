#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
ARANGO_IMAGE="${ARANGO_IMAGE:-arangodb:3.12}"
ARANGO_PASSWORD="${ARANGO_PASSWORD:-testpassword123}"
ARANGO_USER="${ARANGO_USER:-root}"
ARANGO_DB="${ARANGO_DB:-entity_resolution_test}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but not found in PATH" >&2
  exit 1
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "python is required but not found in PATH" >&2
  exit 1
fi

PORT="$("${PYTHON_BIN}" - <<'PY'
import socket
s = socket.socket()
s.bind(("", 0))
port = s.getsockname()[1]
s.close()
print(port)
PY
)"

CONTAINER_NAME="arango-er-tmp-$(date +%s)-$RANDOM"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting temporary ArangoDB container: ${CONTAINER_NAME} on port ${PORT}"
docker run -d \
  --name "${CONTAINER_NAME}" \
  -e ARANGO_ROOT_PASSWORD="${ARANGO_PASSWORD}" \
  -e ARANGO_NO_AUTH=false \
  -p "${PORT}:8529" \
  "${ARANGO_IMAGE}" >/dev/null

echo "Waiting for ArangoDB to become ready..."
ready="false"
for _ in $(seq 1 "${WAIT_SECONDS}"); do
  if curl -u "${ARANGO_USER}:${ARANGO_PASSWORD}" -sS "http://localhost:${PORT}/_api/version" >/dev/null 2>&1; then
    ready="true"
    break
  fi
  sleep 1
done

if [ "${ready}" != "true" ]; then
  echo "ArangoDB did not become ready within ${WAIT_SECONDS}s" >&2
  exit 1
fi

db_response="$(
  curl -u "${ARANGO_USER}:${ARANGO_PASSWORD}" -sS \
    -X POST "http://localhost:${PORT}/_api/database" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${ARANGO_DB}\"}"
)"

"${PYTHON_BIN}" -c 'import json,sys; data=json.loads(sys.argv[1]); sys.exit(1) if data.get("error") is True else None' "${db_response}" || {
  echo "Failed to create database: ${db_response}" >&2
  exit 1
}

echo "Running tests against temp ArangoDB (${PORT})..."
ARANGO_ROOT_PASSWORD="${ARANGO_PASSWORD}" \
ARANGO_USERNAME="${ARANGO_USER}" \
ARANGO_HOST=localhost \
ARANGO_PORT="${PORT}" \
ARANGO_DATABASE="${ARANGO_DB}" \
SKIP_INTEGRATION_TESTS=false \
SKIP_PERFORMANCE_TESTS=false \
pytest "$@"
