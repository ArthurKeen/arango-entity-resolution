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

CONTAINER_NAME="${ARANGO_TEST_CONTAINER_NAME:-arango-entity-resolution-test}"

if docker ps -a --format '{{.Names}}' | python3 -c "import sys; names=set(sys.stdin.read().split()); sys.exit(0 if '${CONTAINER_NAME}' in names else 1)"; then
  echo "Stopping/removing ArangoDB test container: ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null
else
  echo "No ArangoDB test container found: ${CONTAINER_NAME}"
fi

