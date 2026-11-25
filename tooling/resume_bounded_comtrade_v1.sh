#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/ubuntu/CHAOS
OUT="$ROOT/campaigns/agents/trade_v1/raw/comtrade_queries"
for status_file in "$OUT"/*.http_status.txt; do
  [ "$(cat "$status_file")" = 429 ] || continue
  base="${status_file%.http_status.txt}"
  req="$base.request.txt"; file="$base.json"; status="$base.http_status.txt"
  url=$(cat "$req")
  sleep 2
  curl -L --silent --show-error --max-time 45 "$url" -o "$file" -w '%{http_code}' > "$status" || true
  sleep 1
 done
find "$OUT" -name '*.json' -type f -print0 | xargs -0 sha256sum > "$OUT/sha256_manifest_after_resume.txt"
awk '{count[$1]++} END {for (s in count) print s,count[s]}' "$OUT"/*.http_status.txt | sort -n > "$OUT/http_status_summary_after_resume.txt"
cat "$OUT/http_status_summary_after_resume.txt"
