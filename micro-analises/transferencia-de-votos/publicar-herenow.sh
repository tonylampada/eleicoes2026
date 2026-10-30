#!/usr/bin/env bash
# Publica index.html + dados.json desta pasta no here.now (permanente, qualquer um com o link).
# The API key is read from ~/.herenow/credentials at runtime and never printed or stored elsewhere.
set -euo pipefail
cd "$(dirname "$0")"
BASE="https://here.now"; CLIENT="cursor/direct-api"
STATE=".herenow-state.json"
DISPLAY_NAME="Eleições 2026 — transferência de votos 1º→2º turno"
[[ -f "$HOME/.herenow/credentials" ]] || { echo "error: ~/.herenow/credentials missing" >&2; exit 1; }
KEY="$(tr -d '[:space:]' < "$HOME/.herenow/credentials")"
[[ -n "$KEY" ]] || { echo "error: empty credentials" >&2; exit 1; }
api(){ curl -sS -H "Authorization: Bearer ${KEY}" -H "X-HereNow-Client: ${CLIENT}" "$@"; }
ctype(){ case "$1" in *.html) echo "text/html; charset=utf-8";; *.css) echo "text/css; charset=utf-8";; *.js) echo "text/javascript; charset=utf-8";; *.json) echo "application/json; charset=utf-8";; *) echo application/octet-stream;; esac; }
mapfile -t FILES < <(printf "%s\n" index.html dados.json)
FILES_JSON=$(for f in "${FILES[@]}"; do jq -nc --arg p "$f" --argjson s "$(wc -c <"$f")" --arg c "$(ctype "$f")" '{path:$p,size:$s,contentType:$c}'; done | jq -s .)
SLUG=$( [[ -f "$STATE" ]] && jq -r '.slug // empty' "$STATE" || true )
BODY=$(jq -nc --argjson files "$FILES_JSON" --arg dn "$DISPLAY_NAME" '{files:$files, displayName:$dn, spaMode:false, ttlSeconds:null}')
if [[ -n "$SLUG" ]]; then R=$(api -X PUT "$BASE/api/v1/publish/$SLUG" -H "content-type: application/json" -d "$BODY")
else R=$(api -X POST "$BASE/api/v1/publish" -H "content-type: application/json" -d "$(echo "$BODY" | jq 'del(.ttlSeconds)')"); fi
echo "$R" | jq -e '.upload.versionId' >/dev/null || { echo "create/update failed:" >&2; echo "$R" | jq '{code,error,message,details}' >&2; exit 1; }
SLUG=$(echo "$R" | jq -r .slug); VID=$(echo "$R" | jq -r .upload.versionId); FIN=$(echo "$R" | jq -r .upload.finalizeUrl)
echo "create status: $(echo "$R" | jq -c '.status // {}')" >&2
while IFS= read -r row; do
  p=$(echo "$row" | jq -r .path); u=$(echo "$row" | jq -r .url); h=()
  while IFS= read -r k; do [[ -n "$k" ]] && h+=(-H "$k: $(echo "$row" | jq -r --arg k "$k" '.headers[$k]')"); done < <(echo "$row" | jq -r '(.headers // {}) | keys[]')
  echo "$row" | jq -e '(.headers // {}) | keys[] | select(ascii_downcase=="content-type")' >/dev/null 2>&1 || h+=(-H "Content-Type: $(ctype "$p")")
  c=$(curl -sS -o /dev/null -w '%{http_code}' -X PUT "$u" "${h[@]}" --data-binary @"$p"); echo "  upload $p -> $c" >&2
  [[ "$c" =~ ^20[014]$ ]] || { echo "upload failed" >&2; exit 1; }
done < <(echo "$R" | jq -c '.upload.uploads[]')
F=$(api -X POST "$FIN" -H "content-type: application/json" -d "$(jq -nc --arg v "$VID" '{versionId:$v}')")
echo "$F" | jq -e .siteUrl >/dev/null || { echo "finalize failed:" >&2; echo "$F" | jq '{code,error,message}' >&2; exit 1; }
A=$(api -X PATCH "$BASE/api/v1/publish/$SLUG/access" -H "content-type: application/json" -d '{"mode":"anyone_with_link"}')
D=$(api "$BASE/api/v1/publish/$SLUG")
jq -nc --arg slug "$SLUG" --arg url "$(echo "$F" | jq -r .siteUrl)" '{slug:$slug,siteUrl:$url}' > "$STATE"
echo "$F" | jq '{siteUrl, primaryUrl, currentVersionId, status}' > .herenow-finalize.json
echo "$A" | jq '{access: (.access | {mode})}' > .herenow-access.json
echo "$D" | jq '{slug, siteUrl, status, createdAt, expiresAt, currentVersionId, currentVersionSource, displayName, files: [.manifest[]?.path]}' > .herenow-details.json
cat .herenow-finalize.json .herenow-access.json .herenow-details.json
