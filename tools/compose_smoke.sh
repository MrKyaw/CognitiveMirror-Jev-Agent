#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-8000}"
BASE="http://127.0.0.1:${PORT}"
echo "== compose smoke: ${BASE} =="
curl -fsS "${BASE}/health" | head -c 500; echo
curl -fsS -X POST "${BASE}/v1/tools/mirror_user_intent" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-agent-key" \
  -d '{"user_message":"Prepare interview notes for tomorrow","trace_id":"tr_smoke"}' | head -c 500; echo
echo "smoke OK"
