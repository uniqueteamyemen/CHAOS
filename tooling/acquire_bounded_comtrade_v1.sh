#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/ubuntu/CHAOS
OUT="$ROOT/campaigns/agents/trade_v1/raw/comtrade_queries"
mkdir -p "$OUT"
REPORTERS=(36 124 156 276 392)
for reporter in "${REPORTERS[@]}"; do
  for year in $(seq 2000 2024); do
    file="$OUT/reporter_${reporter}_year_${year}.json"
    req="$OUT/reporter_${reporter}_year_${year}.request.txt"
    status="$OUT/reporter_${reporter}_year_${year}.http_status.txt"
    url="https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=${reporter}&period=${year}&cmdCode=TOTAL&flowCode=M&partnerCode=0&partner2Code=0&customsCode=C00&motCode=0&maxRecords=5"
    printf '%s\n' "$url" > "$req"
    curl -L --silent --show-error --max-time 45 "$url" -o "$file" -w '%{http_code}' > "$status" || true
  done
done
find "$OUT" -name '*.json' -type f -print0 | xargs -0 wc -c > "$OUT/size_manifest.txt"
find "$OUT" -name '*.json' -type f -print0 | xargs -0 sha256sum > "$OUT/sha256_manifest.txt"
awk '{count[$1]++} END {for (s in count) print s,count[s]}' "$OUT"/*.http_status.txt | sort -n > "$OUT/http_status_summary.txt"
printf '%s\n' "Completed bounded Comtrade acquisition in $OUT"
cat "$OUT/http_status_summary.txt"
