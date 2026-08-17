#!/bin/bash 

# Exit immediately if any command fails
set -e

# Get current script directory ####
SCRIPT_DIR="$( realpath $(dirname "${BASH_SOURCE[0]}") )"

# Command-line argument usage
print_usage() {
    cat <<USAGE
Usage: $(basename "$0") [-h] [--help] --deploy Local --data_dir <DATA_ROOT> --mira_nf_image <MIRA_NF_IMAGE> [--react_port <REACT_PORT>] [--api_port <API_PORT>]

Arguments:
  Required:
  --deploy <DEPLOY>                 Deployment mode, must be 'Local' for this script. (Default: Local)
  --data_dir <DATA_ROOT>            Path to host directory to store outputs and logs from MIRA applications.
  --mira_nf_image <MIRA_NF_IMAGE>   Docker image (name:tag) to run the MIRA Nextflow pipeline.

  Optional:
  --react_port <REACT_PORT>         Host port to expose MIRA REACT on (Default: 5175). 
                                    If the specified port is in use, an available port will be selected automatically.
  --api_port <API_PORT>             Host port to expose MIRA API on (Default: 8080). 
                                    If the specified port is in use, an available port will be selected automatically.
  -h, --help                        Show this help message and exit.
USAGE
}

usage() {
    print_usage >&2
    exit 1
}

# Initialize variables
DEPLOY="Local"
DATA_ROOT=""
MIRA_NF_IMAGE=""
REACT_PORT="5175"
API_PORT="8080"

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
        --react_port)
            REACT_PORT="$2"
            shift 2
            ;;    
        --api_port)
            API_PORT="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'." >&2
            usage
            ;;
    esac
done

# Make sure required arguments are provided
if [[ -z "${DEPLOY}" || -z "${DATA_ROOT}" || -z "${MIRA_NF_IMAGE}" ]]; then
    MISSING_ARGS=()
    [[ -z "${DEPLOY}" ]] && MISSING_ARGS+=("--deploy")
    [[ -z "${DATA_ROOT}" ]] && MISSING_ARGS+=("--data_dir")
    [[ -z "${MIRA_NF_IMAGE}" ]] && MISSING_ARGS+=("--mira_nf_image")
    echo ""
    echo "Error: Missing required arguments: ${MISSING_ARGS[*]}" >&2
    usage
fi

echo "Checking deployment..."
if [[ "${DEPLOY}" != "Local" ]]; then
    echo "Error: DEPLOY must be 'Local' for this deployment, got '${DEPLOY}'." >&2
    exit 1
fi
echo "Deployment mode: ${DEPLOY}"

echo "Checking data storage..."
if [[ ! -d "${DATA_ROOT}" ]]; then
    echo "Error: The data directory '${DATA_ROOT}' does not exist. Please create it before proceeding." >&2
    exit 1
fi
echo "Data storage directory: ${DATA_ROOT}"

echo "Checking MIRA REACT port..."
if ! [[ "${REACT_PORT}" =~ ^[0-9]+$ ]] || (( REACT_PORT < 1 || REACT_PORT > 65535 )); then
  echo "Error: --react_port must be an integer between 1 and 65535, got '${REACT_PORT}'." >&2
  exit 1
fi

echo "Checking MIRA API port..."
if ! [[ "${API_PORT}" =~ ^[0-9]+$ ]] || (( API_PORT < 1 || API_PORT > 65535 )); then
  echo "Error: --api_port must be an integer between 1 and 65535, got '${API_PORT}'." >&2
  exit 1
fi

# Cache sudo credentials once up front, and keep them alive in the background so the several
# sudo calls below (data storage ownership, Docker install, image pull) don't each re-prompt
echo "Requesting permission to download software and install dependencies. If prompted, please enter the admin password to proceed..."
sudo -v
( while true; do sudo -n true; sleep 60; kill -0 "$$" &> /dev/null || exit; done ) &
SUDO_KEEPALIVE_PID=$!
disown "${SUDO_KEEPALIVE_PID}"

# Make sure the sudo keep-alive loop is stopped no matter how this script exits
cleanup() {
    kill "${SUDO_KEEPALIVE_PID}" &> /dev/null || true
}
trap cleanup EXIT INT TERM

# Only fix ownership (requires sudo) if something under DATA_ROOT isn't already ours
echo "Checking data storage ownership and permissions..."
if find "${DATA_ROOT}" -not -user "$(whoami)" -print -quit | grep -q .; then
    echo "Fixing ownership of ${DATA_ROOT}. If prompted, please enter the admin password to proceed..."
    sudo chown -R "$(id -u):$(id -g)" "${DATA_ROOT}"
fi
find "${DATA_ROOT}" -type d -exec chmod 2775 {} +
find "${DATA_ROOT}" -type f -exec chmod 664 {} +

# Check if micromamba is installed, and if not install it
echo "Checking for Micromamba..."
if ! command -v micromamba &> /dev/null; then
    echo "Micromamba is not installed. Installing micromamba..."
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64)   MICROMAMBA_PLATFORM="linux-64" ;;
        Linux-aarch64)  MICROMAMBA_PLATFORM="linux-aarch64" ;;
        Darwin-x86_64)  MICROMAMBA_PLATFORM="osx-64" ;;
        Darwin-arm64)   MICROMAMBA_PLATFORM="osx-arm64" ;;
        *)
            echo "Error: Unsupported platform '$(uname -s)-$(uname -m)' for Micromamba." >&2
            exit 1
            ;;
    esac
    mkdir -p "${HOME}/bin"
    curl -Ls "https://micro.mamba.pm/api/micromamba/${MICROMAMBA_PLATFORM}/latest" | tar -xvj -C "${HOME}" bin/micromamba
fi

# Initialize micromamba environment
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/micromamba}"
export PATH="${HOME}/bin:${PATH}"
eval "$(micromamba shell hook -s posix)"

# Check if Docker is installed, and if not install it
echo "Checking for Docker..."
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker. If prompted, please enter the admin password to proceed..."
    case "$(uname -s)" in
        Linux)
            curl -fsSL https://get.docker.com | sudo sh
            sudo systemctl enable --now docker
            sudo usermod -aG docker "${USER}"
            echo "Docker was installed. Log out and back in (or run 'newgrp docker') for group changes to take effect. Afterwards, re-run this script to continue the MIRA setup."
            exit 1
            ;;
        Darwin)
            if ! command -v brew &> /dev/null; then
                echo "Error: Homebrew is required to install Docker Desktop on macOS. Install it from https://brew.sh and re-run this script." >&2
                exit 1
            fi
            brew install --cask docker
            open -a Docker
            echo "Waiting for Docker Desktop to start..."
            DOCKER_WAIT_SECONDS=60
            until docker system info &> /dev/null; do
                sleep 2
                DOCKER_WAIT_SECONDS=$((DOCKER_WAIT_SECONDS - 2))
                if [[ ${DOCKER_WAIT_SECONDS} -le 0 ]]; then
                    echo "Error: Docker Desktop did not finish starting. Open it manually from Applications, complete first-time setup, then re-run this script." >&2
                    exit 1
                fi
            done
            ;;
        *)
            echo "Error: Unsupported platform '$(uname -s)' for automatic Docker installation." >&2
            exit 1
            ;;
    esac
fi

# Check if Docker is running and accessible
if ! sudo docker info >/dev/null 2>&1; then
    echo "Error: Docker is installed but the Docker daemon is not running or accessible." >&2
    exit 1
fi
echo "Docker: $(sudo docker --version)"

# Check if the MIRA Nextflow image is available locally, and if not pull it
echo "Checking MIRA Nextflow image. If prompted, please enter the admin password to proceed..."
if ! sudo docker image inspect "${MIRA_NF_IMAGE}" &> /dev/null; then
    if ! sudo docker pull "${MIRA_NF_IMAGE}" &> /dev/null; then
        echo "Error: Failed to pull MIRA Nextflow image '${MIRA_NF_IMAGE}'." >&2
        exit 1
    fi
fi
echo "MIRA Nextflow image: ${MIRA_NF_IMAGE}"

# Check if node is installed, and if not install it via micromamba (works on both Linux and macOS)
echo "Checking for Node.js..."
if ! command -v node &> /dev/null; then
    echo "Node.js is not installed. Installing Node.js via Micromamba..."
    micromamba create -y -n mira_node -c conda-forge nodejs
    export PATH="${MAMBA_ROOT_PREFIX}/envs/mira_node/bin:${PATH}"
fi
echo "Node.js: $(node --version)"

# Check if micromamba environment exists, and if not create it from environment.yml
ENV_NAME="mira_react_env"
ENV_FILE="${SCRIPT_DIR}/environment.yml"
echo "Checking for the '${ENV_NAME}' Python environment..."
if [[ ! -d "${MAMBA_ROOT_PREFIX}/envs/${ENV_NAME}" ]]; then
    echo "Creating Python environment '${ENV_NAME}' from ${ENV_FILE}..."
    micromamba env create -y -n "${ENV_NAME}" -f "${ENV_FILE}"
fi
export PATH="${MAMBA_ROOT_PREFIX}/envs/${ENV_NAME}/bin:${PATH}"
echo "Python: $(python --version) (env: ${ENV_NAME})"

# Close previous pid in pid.log if it exists
PID_FILE="${DATA_ROOT}/logs/pid.log"
if [[ -f "${PID_FILE}" ]]; then
    echo "Closing previous MIRA processes from ${PID_FILE}..."
    while read -r PID; do
        if [[ -n "${PID}" ]] && kill -0 "${PID}" &> /dev/null; then
            echo "Killing process group ${PID}..."
            kill -- "-${PID}" || echo "Warning: Failed to kill process group ${PID}."
            # Wait for the group to actually exit so its ports are released before we
            # check port availability below, instead of racing the still-shutting-down process
            WAIT_SECONDS=10
            while kill -0 "${PID}" &> /dev/null && [[ ${WAIT_SECONDS} -gt 0 ]]; do
                sleep 1
                WAIT_SECONDS=$((WAIT_SECONDS - 1))
            done
            if kill -0 "${PID}" &> /dev/null; then
                # If Process group ${PID} did not exit in time; force it"
                kill -9 -- "-${PID}" || true
                sleep 1
            fi
        fi
    done < "${PID_FILE}"
    rm -f "${PID_FILE}"
fi

# Function to find an available port
find_available_port () {
  local label=$1
  local port=$2
  while lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; do
    new_port=$((RANDOM % 5999 + 4001))
    echo "${label} port ${port} is in use. Trying port ${new_port}..."
    port=${new_port}
  done
  echo ${port}
}

# Check if the REACT port is available, otherwise find an available port
REACT_PORT=$(find_available_port "REACT" "${REACT_PORT}")
API_PORT=$(find_available_port "API" "${API_PORT}")

# Reset frontend build artifacts so npm can rebuild them cleanly
echo "Checking for root-owned files under frontend/node_modules and frontend/dist..."
for FRONTEND_PATH in "${SCRIPT_DIR}/frontend/node_modules" "${SCRIPT_DIR}/frontend/dist"; do
    if [[ -e "${FRONTEND_PATH}" ]] && find "${FRONTEND_PATH}" -not -user "$(whoami)" -print -quit | grep -q .; then
        echo "Found files not owned by $(whoami) under ${FRONTEND_PATH}. Removing it so it can be rebuilt. If prompted, please enter the admin password to proceed..."
        sudo rm -rf "${FRONTEND_PATH}"
    fi
done

# Run the backend and frontend in detached mode
LOG_DIR="${DATA_ROOT}/logs"
mkdir -p "${LOG_DIR}"
API_LOG="${LOG_DIR}/api-kickoff.log"
REACT_LOG="${LOG_DIR}/react-kickoff.log"
PID_FILE="${LOG_DIR}/pid.log"

# setsid makes each wrapper the leader of its own process group, so its PID doubles as a
# group ID we can later kill with `kill -- -PID` to take down uvicorn/npm/vite descendants too
# macOS doesn't have setsid, so we use a perl fallback to emulate it if needed
# Backgrounds exactly once and echoes the real setsid/perl PID; log file must be passed in (not
# applied by the caller) since a caller-side redirect would also swallow the echoed PID
detach() {
    local log_file=$1
    shift
    if command -v setsid &> /dev/null; then
        setsid "$@" > "${log_file}" 2>&1 < /dev/null &
    else
        nohup perl -e 'use POSIX "setsid"; setsid(); exec @ARGV' -- "$@" > "${log_file}" 2>&1 < /dev/null &
    fi
    echo $!
}

API_PID=$(detach "${API_LOG}" bash "${SCRIPT_DIR}/backend/api-kickoff" --deploy "${DEPLOY}" --data_dir "${DATA_ROOT}" --mira_nf_image "${MIRA_NF_IMAGE}" --api_port "${API_PORT}" --react_port "${REACT_PORT}")
disown "${API_PID}" 2>/dev/null || true
echo "${API_PID}" >> "${PID_FILE}"

REACT_PID=$(detach "${REACT_LOG}" bash "${SCRIPT_DIR}/frontend/react-kickoff" --react_port "${REACT_PORT}" --api_port "${API_PORT}")
disown "${REACT_PID}" 2>/dev/null || true
echo "${REACT_PID}" >> "${PID_FILE}"

echo ""
echo "API LOG: ${API_LOG}"
echo "REACT LOG: ${REACT_LOG}"
echo "PID LOG: ${PID_FILE}"
echo ""
echo "MIRA setup is complete!"
echo "MIRA API will be deployed at http://localhost:${API_PORT}, with interactive docs at http://localhost:${API_PORT}/docs/"
echo "MIRA REACT will be deployed at http://localhost:${REACT_PORT}"
echo ""
