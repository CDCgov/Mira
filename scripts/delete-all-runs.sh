#!/usr/bin/env bash
# Delete every MIRA run via the API (GET /list/runs + DELETE /delete/run).
# Requires: curl, jq
set -euo pipefail

API_HOST="${MIRA_API_HOST:-http://localhost}"
API_PORT="${MIRA_API_PORT:-8080}"
ASSUME_YES=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [--host URL] [--port PORT] [-y|--yes]

Deletes ALL runs known to the MIRA API. Files on disk (uploaded FASTQs and
pipeline outputs) are also removed for each run.

By default each run is listed one at a time and you confirm y/n per run.
Use -y/--yes to delete every run without prompting.

Options:
  --host URL   API base URL (default: ${API_HOST}, env: MIRA_API_HOST)
  --port PORT  API port      (default: ${API_PORT}, env: MIRA_API_PORT)
  -y, --yes    Delete all runs without prompting
  -h, --help   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host) API_HOST="$2"; shift 2 ;;
        --port) API_PORT="$2"; shift 2 ;;
        -y|--yes) ASSUME_YES=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
done

command -v curl >/dev/null || { echo "Error: curl is required." >&2; exit 1; }
command -v jq   >/dev/null || { echo "Error: jq is required." >&2; exit 1; }

API="${API_HOST}:${API_PORT}"

echo "Fetching runs from ${API}/list/runs ..."
runs_json="$(curl -fsS "${API}/list/runs")"

# Emit "run_name<TAB>experiment_type" per run.
mapfile -t runs < <(echo "${runs_json}" | jq -r '.run_info[]? | [.run_name, .experiment_type] | @tsv')

if [[ ${#runs[@]} -eq 0 ]]; then
    echo "No runs found. Nothing to delete."
    exit 0
fi

echo "Found ${#runs[@]} run(s)."

failures=0
deleted=0
skipped=0
for r in "${runs[@]}"; do
    IFS=$'\t' read -r name exp <<<"$r"

    if [[ ${ASSUME_YES} -ne 1 ]]; then
        read -r -p "Delete '${name}' (${exp})? [y/N] " reply
        if [[ ! "${reply}" =~ ^[Yy]$ ]]; then
            echo "  skipped."
            skipped=$((skipped + 1))
            continue
        fi
    fi

    echo "Deleting '${name}' (${exp}) ..."
    if curl -fsS -X DELETE "${API}/delete/run" \
        -H "Content-Type: application/json" \
        -d "$(jq -nc --arg n "$name" --arg e "$exp" '{run_name:$n, experiment_type:$e}')" \
        >/dev/null; then
        echo "  deleted."
        deleted=$((deleted + 1))
    else
        echo "  FAILED to delete '${name}'." >&2
        failures=$((failures + 1))
    fi
done

echo "Done: ${deleted} deleted, ${skipped} skipped, ${failures} failed."
[[ ${failures} -eq 0 ]] || exit 1
