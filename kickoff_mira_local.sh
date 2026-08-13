#!/bin/bash 

# Exit immediately if any command fails
set -e

# Get current script directory ####
SCRIPT_DIR="$( realpath $(dirname "${BASH_SOURCE[0]}") )"

# Command-line argument usage
print_usage() {
    cat <<USAGE
Usage: $(basename "$0") [-h] [--help] --deploy Local --data_dir <DATA_ROOT> --mira_nf_image <MIRA_NF_IMAGE> [--host_url <HOST_URL>] [--host <HOST>] [--api_port <API_PORT>] [--react_port <REACT_PORT>]

Arguments:
  Required:
  --deploy <DEPLOY>                 Deployment mode, must be 'Local' or 'Docker'. (Default: Local)
  --data_dir <DATA_ROOT>            Path to the host directory used for MIRA data storage. Must already exist.
  --mira_nf_image <MIRA_NF_IMAGE>   Docker image (name:tag) for the MIRA Nextflow pipeline.

  Optional:
  --host_url <HOST_URL>             Hostname used to build the URLs printed after startup. (Default: localhost)
  --host <HOST>                     Address the backend/frontend servers bind to. (Default: 0.0.0.0)
  --api_port <API_PORT>             Port to run the MIRA backend API on. (Default: 8080)
  --react_port <REACT_PORT>         Port to run the MIRA React frontend on. (Default: 5175)
  -h, --help                        Show this help message and exit.
USAGE
}

usage() {
    print_usage >&2
    exit 1
}

# Initialize deployment variables
DEPLOY="Local"
DATA_ROOT=""
MIRA_NF_IMAGE=""

# Initialize app variables
HOST_URL="localhost"
HOST="0.0.0.0"
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
        --host_url)
            HOST_URL="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
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

echo "Checking data storage..."
if [[ ! -d "${DATA_ROOT}" ]]; then
    echo "Error: The data directory '${DATA_ROOT}' does not exist. Please create it before proceeding." >&2
    exit 1
fi
echo "Data storage directory: ${DATA_ROOT}"

# Only fix ownership (requires sudo) if something under DATA_ROOT isn't already ours
echo "Checking data storage ownership and permissions..."
if find "${DATA_ROOT}" -not -user "$(whoami)" -print -quit | grep -q .; then
    echo "Fixing ownership of ${DATA_ROOT}. If prompted, please enter the admin password to proceed..."
    sudo chown -R "$(id -u):$(id -g)" "${DATA_ROOT}"
fi
chmod -R 775 "${DATA_ROOT}"

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
            echo "Docker was installed. Log out and back in (or run 'newgrp docker') for group changes to take effect."
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
echo "Docker: $(docker --version)"

# Check if Docker Compose (the 'docker compose' plugin, bundled with modern Docker installs) is available
echo "Checking for Docker Compose..."
if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose plugin is not available. Please update Docker/Docker Desktop to a version that includes 'docker compose'." >&2
    exit 1
fi
echo "Docker Compose: $(docker compose version --short)"

# Check if the MIRA Nextflow image is available locally, and if not pull it
echo "Checking MIRA Nextflow image. If prompted, please enter the admin password to proceed..."
if ! sudo docker inspect "${MIRA_NF_IMAGE}" &> /dev/null; then
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
  # Make sure the port is an interger
  if ! [[ "${port}" =~ ^[0-9]+$ ]]; then
    echo "Error: ${label} port '${port}' is not a valid integer." >&2
    exit 1
  fi
  local check_port=$(echo -n $(lsof -i:${port}) | wc -m)
  while [ ${check_port} -gt 0 ]
  do
    port=$(printf "%04d" $(( RANDOM % 5999 + 4001 )))
    check_port=$(echo -n $(lsof -i:${port}) | wc -m)
  done
  echo ${port}
}

# Check if the requested ports are available
API_PORT=$(find_available_port "API" "${API_PORT}")
REACT_PORT=$(find_available_port "REACT" "${REACT_PORT}")

# Reset frontend build artifacts left root-owned by a previous Docker-based run, so npm can rebuild them cleanly
echo "Checking for root-owned files under frontend/node_modules and frontend/dist..."
for FRONTEND_PATH in "${SCRIPT_DIR}/frontend/node_modules" "${SCRIPT_DIR}/frontend/dist"; do
    if [[ -e "${FRONTEND_PATH}" ]] && find "${FRONTEND_PATH}" -not -user "$(whoami)" -print -quit | grep -q .; then
        echo "Found files not owned by $(whoami) under ${FRONTEND_PATH}. Removing it so it can be rebuilt. If prompted, please enter the admin password to proceed..."
        sudo rm -rf "${FRONTEND_PATH}"
    fi
done

# Run the backend and frontend setup scripts fully detached (survive this script/terminal exiting)
LOG_DIR="${DATA_ROOT}/logs"
mkdir -p "${LOG_DIR}"
API_LOG="${LOG_DIR}/api-kickoff.log"
REACT_LOG="${LOG_DIR}/react-kickoff.log"
PID_FILE="${LOG_DIR}/pid.log"

# setsid makes each wrapper the leader of its own process group, so its PID doubles as a
# group ID we can later kill with `kill -- -PID` to take down uvicorn/npm/vite descendants too
setsid nohup bash "${SCRIPT_DIR}/backend/api-kickoff" --deploy "${DEPLOY}" --data_dir "${DATA_ROOT}" --mira_nf_image "${MIRA_NF_IMAGE}" --host_url "${HOST_URL}" --host "${HOST}" --api_port "${API_PORT}" --react_port "${REACT_PORT}" > "${API_LOG}" 2>&1 &
API_PID=$!
disown "${API_PID}"
echo "${API_PID}" >> "${PID_FILE}"

setsid nohup bash "${SCRIPT_DIR}/frontend/react-kickoff" --host_url "${HOST_URL}" --host "${HOST}" --react_port "${REACT_PORT}" --api_port "${API_PORT}" > "${REACT_LOG}" 2>&1 &
REACT_PID=$!
disown "${REACT_PID}"
echo "${REACT_PID}" >> "${PID_FILE}"

echo ""
echo "API LOG: ${API_LOG}"
echo "REACT LOG: ${REACT_LOG}"
echo "PID LOG: ${PID_FILE}"
echo ""
echo "MIRA setup is complete!"
echo "MIRA API will be deployed at http://${HOST_URL}:${API_PORT}, with interactive docs at http://${HOST_URL}:${API_PORT}/docs/"
echo "MIRA REACT will be deployed at http://${HOST_URL}:${REACT_PORT}"
echo ""
