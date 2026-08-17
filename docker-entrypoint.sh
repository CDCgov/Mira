#!/bin/bash

# Exit immediately if any command fails
set -e

# Get current script directory ####
SCRIPT_DIR="$( realpath $(dirname "${BASH_SOURCE[0]}") )"

# Command-line argument usage
print_usage() {
    cat <<USAGE
Usage: $(basename "$0") [-h] [--help] --deploy <DEPLOY> --data_dir <DATA_ROOT> --mira_nf_image <MIRA_NF_IMAGE> --api_port <API_PORT> --react_port <REACT_PORT>

Arguments:
    --deploy <DEPLOY>                 Deployment mode, must be 'Docker' for this script. (Default: Docker)
    --data_dir <DATA_ROOT>            Path to host directory to store outputs from MIRA applications. Must already exist.
    --mira_nf_image <MIRA_NF_IMAGE>   Docker image to run the MIRA Nextflow pipeline.
    --api_port <API_PORT>             Host port to expose the MIRA backend API on. (Default: 8080)
    --react_port <REACT_PORT>         Host port to expose the MIRA React frontend on. (Default: 5175)
    -h, --help                        Show this help message and exit.
USAGE
}

usage() {
    print_usage >&2
    exit 1
}

# Initialize variables
DEPLOY="Docker"
DATA_ROOT=""
MIRA_NF_IMAGE=""
API_PORT="8080"
REACT_PORT="5175"

# Parse named arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            print_usage
            exit 0
            ;;
        --deploy)
            DEPLOY="$2"
            shift 2
            ;;
        --data_dir)
            DATA_ROOT="$2"
            shift 2
            ;;
        --mira_nf_image)
            MIRA_NF_IMAGE="$2"
            shift 2
            ;;
        --api_port)
            API_PORT="$2"
            shift 2
            ;;
        --react_port)
            REACT_PORT="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'." >&2
            usage
            ;;
    esac
done

# Only --deploy, --data_dir and --mira_nf_image are required; the rest have defaults
if [[ -z "${DEPLOY}" || -z "${DATA_ROOT}" || -z "${MIRA_NF_IMAGE}" || -z "${API_PORT}" || -z "${REACT_PORT}" ]]; then
    MISSING_ARGS=()
    [[ -z "${DEPLOY}" ]] && MISSING_ARGS+=("--deploy")
    [[ -z "${DATA_ROOT}" ]] && MISSING_ARGS+=("--data_dir")
    [[ -z "${MIRA_NF_IMAGE}" ]] && MISSING_ARGS+=("--mira_nf_image")
    [[ -z "${REACT_PORT}" ]] && MISSING_ARGS+=("--react_port")
    [[ -z "${API_PORT}" ]] && MISSING_ARGS+=("--api_port")
    echo ""
    echo "Error: Missing required arguments: ${MISSING_ARGS[*]}" >&2
    usage
fi

# Validate --deploy argument
if [[ "${DEPLOY}" != "Docker" ]]; then
    echo ""
    echo "Error: Invalid value for --deploy. Must be 'Docker' for this script." >&2
    usage
fi
echo "Deployment mode: ${DEPLOY}"

echo "Checking data storage..."
if [[ ! -d "${DATA_ROOT}" ]]; then
    echo "Error: The data directory '${DATA_ROOT}' does not exist. Please create it before proceeding." >&2
    exit 1
fi
echo "Data storage directory: ${DATA_ROOT}"

# Create logs directory 
mkdir -p "${DATA_ROOT}/logs"

# Launch the backend in the background and capturing their outputs to a log file
${SCRIPT_DIR}/backend/api-kickoff \
  --deploy "${DEPLOY}" \
  --data_dir "${DATA_ROOT}" \
  --mira_nf_image "${MIRA_NF_IMAGE}" \
  --api_port "${API_PORT}" \
  --react_port "${REACT_PORT}" \
  > "${DATA_ROOT}/logs/api-kickoff.log" 2>&1 &
backend_pid=$!

# Launch the frontend in the background and capturing their outputs to a log file
${SCRIPT_DIR}/frontend/react-kickoff \
  --react_port "${REACT_PORT}" \
  --api_port "${API_PORT}" \
  > "${DATA_ROOT}/logs/react-kickoff.log" 2>&1 &
frontend_pid=$!

# Save process IDs to a file
echo "$backend_pid" > "${DATA_ROOT}/logs/pid.log"
echo "$frontend_pid" >> "${DATA_ROOT}/logs/pid.log"

# Set up a trap to kill the background processes when the script exits
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' INT TERM EXIT

# Wait for either process to exit and capture the exit status
wait -n "$backend_pid" "$frontend_pid"
status=$?
kill "$backend_pid" "$frontend_pid" 2>/dev/null || true
wait || true
exit "$status"