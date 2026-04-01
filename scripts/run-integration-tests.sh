#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "==> Building and starting Docker Compose stack..."
docker compose up --build -d

echo "==> Waiting for backend to be ready (up to 60s)..."
TIMEOUT=60
ELAPSED=0
until curl -sf http://localhost:8000/strategies > /dev/null 2>&1; do
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: Backend did not become ready within ${TIMEOUT}s"
    docker compose down -v
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
echo "    Backend is ready (${ELAPSED}s elapsed)"

echo "==> Running database migrations..."
docker compose exec -T backend alembic upgrade head

echo "==> Running integration tests..."
set +e
python -m pytest tests/integration/ -v -m integration --timeout=60
TEST_EXIT_CODE=$?
set -e

echo "==> Tearing down Docker Compose stack..."
docker compose down -v

echo "==> Done. Exit code: $TEST_EXIT_CODE"
exit $TEST_EXIT_CODE
