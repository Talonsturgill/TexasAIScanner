#!/usr/bin/env bash
# Stand the scan backend up, or bring it level with this checkout. Safe to re-run.
#
# WHAT IT WILL NOT DO: set the four secrets. Those go in through `wrangler secret put`, which
# reads stdin, so they are never written to a file or a shell history and never pass through
# anybody's chat transcript. The script prints the four lines to run and stops short of running
# them, which is the honest place for a script to stop.
#
#   CLOUDFLARE_API_TOKEN=...  bash workers/scan/deploy.sh
#
# The token needs three permissions, and no more:
#   Account / Workers Scripts / Edit
#   Account / D1 / Edit
#   Account / Workers KV Storage / Edit    (wrangler uses it for the deploy bookkeeping)
set -euo pipefail
cd "$(dirname "$0")"

WR="npx --yes wrangler@4"
DB="texas-scan"

[ -n "${CLOUDFLARE_API_TOKEN:-}" ] || {
  echo "CLOUDFLARE_API_TOKEN is unset. Nothing here can reach Cloudflare without it." >&2
  exit 2
}

echo "==> the bundle is current with the modules"
node bundle.mjs
node test.js | tail -1

echo "==> the database"
# `d1 create` fails if it already exists, which is the correct behaviour and the wrong exit
# code for a script that is meant to be re-runnable, so an existing database is not an error.
$WR d1 create "$DB" 2>/dev/null || echo "    already there"

ID=$($WR d1 info "$DB" --json | python3 -c 'import sys,json; print(json.load(sys.stdin)["uuid"])')
[ -n "$ID" ] || { echo "could not read the database id" >&2; exit 1; }
echo "    $DB is $ID"

# Written into the committed toml rather than exported, so the next person deploying gets the
# same database instead of quietly creating a second one. The id is not a credential.
python3 - "$ID" <<'PY'
import pathlib, re, sys
p = pathlib.Path("wrangler.toml")
s = p.read_text()
new = re.sub(r'database_id = "[^"]*"', f'database_id = "{sys.argv[1]}"', s)
p.write_text(new)
print("    wrangler.toml pinned to it" if new != s else "    wrangler.toml already pinned")
PY

echo "==> the schema, which is idempotent"
$WR d1 execute "$DB" --remote --file ../../db/d1_schema.sql

echo "==> the worker"
$WR deploy

echo
echo "STILL TO DO, and only you can: the four secrets."
echo "Each of these prompts for one value and reads it from stdin, so it is not stored here."
echo
echo "    npx wrangler@4 secret put TRIGGER_URL       # .../routines/<id>/fire"
echo "    npx wrangler@4 secret put TRIGGER_SECRET    # fires the ROUTINE, not the API"
echo "    npx wrangler@4 secret put TURNSTILE_SECRET  # the one paired with the site key"
echo "    npx wrangler@4 secret put PROGRESS_SECRET   # generate: openssl rand -hex 32"
echo
echo "Then set SCAN_PROGRESS_URL and SCAN_PROGRESS_SECRET in the routine's environment."
echo "Until the trigger is set, /request answers \"scanner not fully configured\" and says so."
