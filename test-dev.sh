#!/usr/bin/env bash
#
# test-dev.sh - rerun every MIRA run under ~/mira-local-data through the dev
#               stack, using your LOCAL code for all three repos:
#
#                 * MIRA      (backend + frontend)  -> bind-mounted by compose
#                 * mira-oxide (Rust binary)        -> COMPILED here, then mounted
#                 * Mira-nf   (Nextflow pipeline)   -> bind-mounted by compose
#
# It brings up docker-compose-dev-ben.yml (which bind-mounts the three repos into
# the `mira` container), discovers every run directory, and re-executes the
# MIRA-NF pipeline for each one with the exact command the backend uses
# (`-profile mira_nf_container`), so the locally-built mira-oxide binary is
# overlaid into every process via MIRA_OXIDE_DEV_BIND.
#
# Usage:
#   ./test-dev.sh [options]
#
# Options / env overrides:
#   --list                Discover + print the runs and commands, then exit (no build, no run).
#   --skip-build          Reuse the existing mira-oxide/target/dev-linux binary (skip cargo/docker build).
#   --no-nextclade        Do not pass --nextclade true.
#   --no-parquet          Do not pass --parquet_files true.
#   --down                Tear the compose stack down when finished (default: leave it up).
#   --filter <glob>       Only run runs whose run-id matches the shell glob (e.g. '*Flu-Illumina*').
#   DATA_ROOT=<path>      Data root to scan (default: ~/mira-local-data).
#
# Per-run, pipeline console output is written to <run>/nextflow.stdout.log (same
# file the dashboard parses). A summary log for this invocation is written to
# ./nf_status/test-dev_<timestamp>.log.
#
# Exit code is non-zero if any run fails.

set -uo pipefail

#############################################
# Paths / config
#############################################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIRA_DIR="$SCRIPT_DIR"
OXIDE_DIR="$(cd "$MIRA_DIR/../mira-oxide" 2>/dev/null && pwd || true)"
MNF_DIR="$(cd "$MIRA_DIR/../Mira-nf" 2>/dev/null && pwd || true)"
COMPOSE_FILE="$MIRA_DIR/docker-compose-dev-ben.yml"
CONTAINER="mira"
DATA_ROOT="${DATA_ROOT:-$HOME/mira-local-data}"

OXIDE_IMAGE="mira-oxide:dev-local"
OXIDE_BIN_OUT="$OXIDE_DIR/target/dev-linux/mira-oxide"   # path the compose mounts read-only

# Defaults (togglable via flags)
DO_BUILD=1
DO_LIST=0
DO_DOWN=0
WANT_NEXTCLADE=1
WANT_PARQUET=1
RUN_FILTER='*'

#############################################
# Args
#############################################
while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)         DO_LIST=1 ;;
    --skip-build)   DO_BUILD=0 ;;
    --no-nextclade) WANT_NEXTCLADE=0 ;;
    --no-parquet)   WANT_PARQUET=0 ;;
    --down)         DO_DOWN=1 ;;
    --filter)       shift; RUN_FILTER="${1:-*}" ;;
    -h|--help)      sed -n '2,40p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "!! unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

c_red=$'\033[31m'; c_grn=$'\033[32m'; c_ylw=$'\033[33m'; c_dim=$'\033[2m'; c_rst=$'\033[0m'
say()  { printf '%s\n' ">> $*"; }
warn() { printf '%s\n' "${c_ylw}!! $*${c_rst}" >&2; }
die()  { printf '%s\n' "${c_red}!! $*${c_rst}" >&2; exit 1; }

#############################################
# Sanity checks
#############################################
[[ -n "$OXIDE_DIR" ]] || die "mira-oxide repo not found next to MIRA (expected $MIRA_DIR/../mira-oxide)"
[[ -n "$MNF_DIR"   ]] || die "Mira-nf repo not found next to MIRA (expected $MIRA_DIR/../Mira-nf)"
[[ -f "$COMPOSE_FILE" ]] || die "compose file not found: $COMPOSE_FILE"
[[ -d "$DATA_ROOT/MIRA" ]] || die "no MIRA data under $DATA_ROOT/MIRA"
command -v docker >/dev/null 2>&1 || die "docker not found on PATH"

# experiment_type from <Pathogen>/<Platform>; SC2 defaults to Whole-Genome.
# A run dir may override by placing the exact type in a file named `.experiment_type`.
map_experiment_type() {
  local pathogen="$1" platform="$2" run_dir="$3"
  if [[ -f "$run_dir/.experiment_type" ]]; then
    tr -d '[:space:]' < "$run_dir/.experiment_type"; return
  fi
  case "$pathogen/$platform" in
    Flu/ONT)       echo "Flu-ONT" ;;
    Flu/Illumina)  echo "Flu-Illumina" ;;
    RSV/ONT)       echo "RSV-ONT" ;;
    RSV/Illumina)  echo "RSV-Illumina" ;;
    SC2/ONT)       echo "SC2-Whole-Genome-ONT" ;;
    SC2/Illumina)  echo "SC2-Whole-Genome-Illumina" ;;
    *)             echo "" ;;
  esac
}

#############################################
# Discover runs (host side): $DATA_ROOT/MIRA/<Pathogen>/<Platform>/<run>/samplesheet.csv
#############################################
declare -a RUN_DIRS=()
while IFS= read -r ss; do
  RUN_DIRS+=("$(dirname "$ss")")
done < <(find "$DATA_ROOT/MIRA" -mindepth 4 -maxdepth 4 -name samplesheet.csv 2>/dev/null | sort)

[[ ${#RUN_DIRS[@]} -gt 0 ]] || die "no runs (…/MIRA/<Pathogen>/<Platform>/<run>/samplesheet.csv) found under $DATA_ROOT"

say "MIRA repo   : $MIRA_DIR"
say "mira-oxide  : $OXIDE_DIR"
say "Mira-nf     : $MNF_DIR"
say "data root   : $DATA_ROOT   (mounted as /data in the container)"
say "runs found  : ${#RUN_DIRS[@]}   filter='$RUN_FILTER'"
echo

#############################################
# --list: print planned commands and exit
#############################################
if [[ "$DO_LIST" == 1 ]]; then
  for run_dir in "${RUN_DIRS[@]}"; do
    run_id="$(basename "$run_dir")"
    [[ "$run_id" == $RUN_FILTER ]] || continue
    platform="$(basename "$(dirname "$run_dir")")"
    pathogen="$(basename "$(dirname "$(dirname "$run_dir")")")"
    etype="$(map_experiment_type "$pathogen" "$platform" "$run_dir")"
    crun="/data/${run_dir#"$DATA_ROOT"/}"
    if [[ -z "$etype" ]]; then
      printf '%s  %s\n' "${c_ylw}SKIP${c_rst}" "$run_id (unknown type $pathogen/$platform)"
      continue
    fi
    printf '%sRUN %s  %s%s[%s]%s\n' "$c_grn" "$c_rst" "$run_id" "$c_dim" "$etype" "$c_rst"
    printf '     %snextflow run /MIRA-NF/main.nf -profile mira_nf_container --check_version false --input %s/samplesheet.csv --runpath %s --outdir %s/outputs --e %s%s%s%s\n' \
      "$c_dim" "$crun" "$crun" "$crun" "$etype" \
      "$([[ $WANT_PARQUET == 1 ]] && echo ' --parquet_files true')" \
      "$([[ $WANT_NEXTCLADE == 1 ]] && echo ' --nextclade true')" "$c_rst"
  done
  exit 0
fi

#############################################
# 1) Compile mira-oxide -> linux/amd64 binary the compose mounts
#############################################
if [[ "$DO_BUILD" == 1 ]]; then
  say "Compiling mira-oxide (linux/amd64) from local source…"
  docker build --platform linux/amd64 -t "$OXIDE_IMAGE" "$OXIDE_DIR" \
    || die "mira-oxide docker build failed"
  mkdir -p "$(dirname "$OXIDE_BIN_OUT")"
  cid="$(docker create --platform linux/amd64 "$OXIDE_IMAGE")" || die "docker create failed"
  # Extract into a temp file, then overwrite in place (preserve the path the mount targets).
  tmp_bin="$(mktemp)"
  docker cp "$cid:/app/mira-oxide" "$tmp_bin" || { docker rm -f "$cid" >/dev/null 2>&1; die "docker cp failed"; }
  docker rm -f "$cid" >/dev/null 2>&1 || true
  install -m 0755 "$tmp_bin" "$OXIDE_BIN_OUT" && rm -f "$tmp_bin"
  say "mira-oxide binary -> $OXIDE_BIN_OUT"
  file "$OXIDE_BIN_OUT" | sed 's/^/   /'
else
  [[ -x "$OXIDE_BIN_OUT" ]] || die "--skip-build set but no binary at $OXIDE_BIN_OUT"
  say "Reusing existing mira-oxide binary: $OXIDE_BIN_OUT"
fi
echo

#############################################
# 2) Bring up the dev stack (local MIRA + Mira-nf + mira-oxide)
#############################################
docker image inspect mira:latest >/dev/null 2>&1 \
  || die "image 'mira:latest' not found — build/pull it first (see docker-compose-dev-ben.yml header)"

say "Starting dev stack via $(basename "$COMPOSE_FILE")…"
# Force-recreate so the container re-binds the freshly built mira-oxide binary.
docker compose -f "$COMPOSE_FILE" up -d --force-recreate \
  || die "docker compose up failed"

# Wait for the container to be running.
for _ in $(seq 1 30); do
  [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" == "true" ]] && break
  sleep 1
done
[[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" == "true" ]] \
  || die "container '$CONTAINER' did not start"
say "container '$CONTAINER' is up"
echo

#############################################
# 3) Rerun every run inside the container
#############################################
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$MIRA_DIR/nf_status"
SUMMARY_LOG="$MIRA_DIR/nf_status/test-dev_${STAMP}.log"
: >"$SUMMARY_LOG"

n_ok=0; n_fail=0; n_skip=0
declare -a FAILED=()

for run_dir in "${RUN_DIRS[@]}"; do
  run_id="$(basename "$run_dir")"
  [[ "$run_id" == $RUN_FILTER ]] || continue
  platform="$(basename "$(dirname "$run_dir")")"
  pathogen="$(basename "$(dirname "$(dirname "$run_dir")")")"
  etype="$(map_experiment_type "$pathogen" "$platform" "$run_dir")"
  crun="/data/${run_dir#"$DATA_ROOT"/}"

  if [[ -z "$etype" ]]; then
    warn "SKIP $run_id — cannot map $pathogen/$platform to an experiment type"
    echo "SKIP  $run_id  ($pathogen/$platform)" >>"$SUMMARY_LOG"
    n_skip=$((n_skip+1)); continue
  fi

  extra=""
  [[ $WANT_PARQUET   == 1 ]] && extra+=" --parquet_files true"
  [[ $WANT_NEXTCLADE == 1 ]] && extra+=" --nextclade true"

  say "${c_grn}RUN${c_rst} $run_id  [$etype]  -> $crun/nextflow.stdout.log"
  start=$(date +%s)
  # Mirror the backend command; run it inside the live container. Console output
  # (incl. the Nextflow completion summary) lands in the run's stdout log.
  if docker exec "$CONTAINER" bash -lc "
        cd '$crun' &&
        nextflow run /MIRA-NF/main.nf \
          -profile mira_nf_container \
          --check_version false \
          --input '$crun/samplesheet.csv' \
          --runpath '$crun' \
          --outdir '$crun/outputs' \
          --e '$etype'${extra}
      " >"$run_dir/nextflow.stdout.log" 2>&1; then
    dur=$(( $(date +%s) - start ))
    say "  ${c_grn}OK${c_rst}   $run_id  (${dur}s)"
    echo "OK    $run_id  [$etype]  ${dur}s" >>"$SUMMARY_LOG"
    n_ok=$((n_ok+1))
  else
    dur=$(( $(date +%s) - start ))
    warn "  FAIL $run_id  (${dur}s) — see $run_dir/nextflow.stdout.log"
    tail -n 15 "$run_dir/nextflow.stdout.log" | sed 's/^/     /'
    echo "FAIL  $run_id  [$etype]  ${dur}s" >>"$SUMMARY_LOG"
    FAILED+=("$run_id"); n_fail=$((n_fail+1))
  fi
  echo
done

#############################################
# 4) Summary / teardown
#############################################
say "==== test-dev summary (ok=$n_ok fail=$n_fail skip=$n_skip) ===="
cat "$SUMMARY_LOG"
say "summary log: $SUMMARY_LOG"

if [[ "$DO_DOWN" == 1 ]]; then
  say "Tearing down dev stack…"
  docker compose -f "$COMPOSE_FILE" down
else
  say "Dev stack left running (frontend 5175 / api 8080). Use: docker compose -f $(basename "$COMPOSE_FILE") down"
fi

[[ ${#FAILED[@]} -eq 0 ]] || { warn "failed runs: ${FAILED[*]}"; exit 1; }
exit 0
