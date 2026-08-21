#!/bin/bash

# Exit immediately if any command fails
set -e

# Command-line argument usage
print_usage() {
    cat <<USAGE
Usage: $(basename "$0") [-h] [--help] --deploy Docker --data_dir <DATA_ROOT> --mira_image <MIRA_IMAGE> [--react_port <REACT_PORT>] [--api_port <API_PORT>]

Arguments:
  Required:
  --deploy <DEPLOY>                 Deployment mode, must be 'Docker' for this script. (Default: Docker)
  --data_dir <DATA_ROOT>            Path to host directory to store outputs and logs from MIRA applications.
  --mira_image <MIRA_IMAGE>         Docker image (name:tag) for the MIRA API + REACT application.

  Optional:
  --react_port <REACT_PORT>         Host port to expose MIRA REACT on (Default: 5175). 
                                    If the specified port is in use, an available port will be selected automatically.
  --api_port <API_PORT>             Host port to expose MIRA API on (Default: None). 
                                    If a port is specified and is in use, an available port will be selected automatically.
  --codebase <MIRA_CODEBASE>        Path to a local MIRA codebase to bind-mount over /MIRA in the
                                    container for development (live edits). Omit for a normal run.
  --sudo                            Run docker/install commands with sudo. Off by default
                                    (Docker Desktop on macOS does not need it).
  -h, --help                        Show help message and exit.
USAGE
}

usage() {
    print_usage >&2
    exit 1
}

# Initialize variables
DEPLOY="Docker"
DATA_ROOT=""
MIRA_IMAGE=""
REACT_PORT="5175"
API_PORT=""
MIRA_CODEBASE=""
USE_SUDO=false

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
        --mira_image)
            MIRA_IMAGE="$2"
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
        --codebase)
            MIRA_CODEBASE="$2"
            shift 2
            ;;
        --sudo)
            USE_SUDO=true
            shift
            ;;
        *)
            echo "Error: Unknown argument '$1'." >&2
            usage
            ;;
    esac
done

# Make sure required arguments are provided
if [[ -z "${DEPLOY}" || -z "${DATA_ROOT}" || -z "${MIRA_IMAGE}" ]]; then
    MISSING_ARGS=()
    [[ -z "${DEPLOY}" ]] && MISSING_ARGS+=("--deploy")
    [[ -z "${DATA_ROOT}" ]] && MISSING_ARGS+=("--data_dir")
    [[ -z "${MIRA_IMAGE}" ]] && MISSING_ARGS+=("--mira_image")
    echo ""
    echo "Error: Missing required arguments: ${MISSING_ARGS[*]}" >&2
    usage
fi

echo "Checking deployment..."
if [[ "${DEPLOY}" != "Docker" ]]; then
    echo "Error: DEPLOY must be 'Docker' for this deployment, got '${DEPLOY}'." >&2
    exit 1
fi
echo "Deployment mode: ${DEPLOY}"

echo "Checking data storage..."
if [[ ! -d "${DATA_ROOT}" ]]; then
    echo "Error: The data directory '${DATA_ROOT}' does not exist. Please create it before proceeding." >&2
    exit 1
fi
echo "Data storage directory: ${DATA_ROOT}"

echo "Checking REACT port..."
if ! [[ "${REACT_PORT}" =~ ^[0-9]+$ ]] || (( REACT_PORT < 1 || REACT_PORT > 65535 )); then
  echo "Error: --react_port must be an integer between 1 and 65535, got '${REACT_PORT}'." >&2
  exit 1
fi

# Check API port if provided
if [[ -n "${API_PORT}" ]]; then
    if ! [[ "${API_PORT}" =~ ^[0-9]+$ ]] || (( API_PORT < 1 || API_PORT > 65535 )); then
        echo "Error: --api_port must be an integer between 1 and 65535, got '${API_PORT}'." >&2
        exit 1
    fi
fi

# Check the development codebase mount if provided
if [[ -n "${MIRA_CODEBASE}" ]]; then
    if [[ ! -d "${MIRA_CODEBASE}" ]]; then
        echo "Error: --codebase directory '${MIRA_CODEBASE}' does not exist." >&2
        exit 1
    fi
    if [[ ! -d "${MIRA_CODEBASE}/backend" || ! -d "${MIRA_CODEBASE}/frontend" ]]; then
        echo "Error: --codebase '${MIRA_CODEBASE}' does not look like a MIRA repo (missing backend/ or frontend/)." >&2
        exit 1
    fi
    MIRA_CODEBASE=$(cd "${MIRA_CODEBASE}" && pwd)   # normalize to an absolute path for the bind mount
    echo "Development codebase mount: ${MIRA_CODEBASE}/{backend,frontend} -> /MIRA/{backend,frontend} (live edits)"
fi

# Prefix for privileged commands. Empty by default; set to "sudo" only with --sudo.
SUDO=""
[[ "${USE_SUDO}" == true ]] && SUDO="sudo"

# When using sudo, cache credentials once up front and keep them alive so the several sudo
# calls below (data storage ownership, Docker install, image pull) don't each re-prompt.
SUDO_KEEPALIVE_PID=""
if [[ -n "${SUDO}" ]]; then
    echo "Requesting permission to download software and install dependencies. If prompted, please enter the admin password to proceed..."
    sudo -v
    ( while true; do sudo -n true; sleep 60; kill -0 "$$" &> /dev/null || exit; done ) &
    SUDO_KEEPALIVE_PID=$!
    disown "${SUDO_KEEPALIVE_PID}"
fi

# Make sure the sudo keep-alive loop is stopped no matter how this script exits
cleanup() {
    [[ -n "${SUDO_KEEPALIVE_PID}" ]] && kill "${SUDO_KEEPALIVE_PID}" &> /dev/null || true
}
trap cleanup EXIT INT TERM

# Only fix ownership (requires sudo) if something under DATA_ROOT isn't already ours
echo "Checking data storage ownership and permissions..."
if find "${DATA_ROOT}" -not -user "$(whoami)" -print -quit | grep -q .; then
    echo "Fixing ownership of ${DATA_ROOT}. If prompted, please enter the admin password to proceed..."
    ${SUDO} chown -R "$(id -u):$(id -g)" "${DATA_ROOT}"
fi
find "${DATA_ROOT}" -type d -exec chmod 2775 {} +
find "${DATA_ROOT}" -type f -exec chmod 664 {} +

# Check software requirements before proceeding
echo "Checking for Docker..."
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker. If prompted, please enter the admin password to proceed..."
    case "$(uname -s)" in
        Linux)
            curl -fsSL https://get.docker.com | ${SUDO} sh
            ${SUDO} systemctl enable --now docker
            ${SUDO} usermod -aG docker "${USER}"
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
if ! ${SUDO} docker info >/dev/null 2>&1; then
    echo "Error: Docker is installed but the Docker daemon is not running or accessible." >&2
    exit 1
fi
echo "Docker: $(${SUDO} docker --version)"

# Check if Docker Compose (the 'docker compose' plugin, bundled with modern Docker installs) is available
echo "Checking for Docker Compose..."
if ! ${SUDO} docker compose version &> /dev/null; then
    echo "Error: Docker Compose plugin is not available. Please update Docker/Docker Desktop to a version that includes 'docker compose'." >&2
    exit 1
fi
echo "Docker Compose: $(${SUDO} docker compose version --short)"

# Check if the MIRA image is available locally, and if not pull it
echo "Checking MIRA image. If prompted, please enter the admin password to proceed..."
if ! ${SUDO} docker image inspect "${MIRA_IMAGE}" &> /dev/null; then
    if ! ${SUDO} docker pull "${MIRA_IMAGE}" &> /dev/null; then
        echo "Error: Failed to pull MIRA image '${MIRA_IMAGE}'." >&2
        exit 1
    fi
fi
echo "MIRA Image: ${MIRA_IMAGE}"

# Function to find an available port
find_available_port () {
  local port=$1
  while lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; do
    new_port=$((RANDOM % 5999 + 4001))
    echo "Port ${port} is in use. Trying port ${new_port}..." >&2
    port=${new_port}
  done
  echo ${port}
}

# Check if the REACT port is available, otherwise find an available port
REACT_PORT=$(find_available_port "${REACT_PORT}")

# If API_PORT is provided, check if it's available, otherwise find an available port
if [[ -n "${API_PORT}" ]]; then
    API_PORT=$(find_available_port "${API_PORT}")
fi

echo "Configure docker-compose.yml file to initialize the containers..."

# Build the optional development mount. The image declares /MIRA/frontend and /MIRA/backend
# as VOLUMEs, so binding the /MIRA parent alone is shadowed by anonymous volumes; bind the two
# source dirs explicitly to override them. An anonymous volume keeps the image's frontend
# node_modules (host deps may be a different arch/absent), and polling makes reload work.
CODEBASE_VOLUME_BLOCK=""
DEV_ENV_BLOCK=""
if [[ -n "${MIRA_CODEBASE}" ]]; then
  CODEBASE_VOLUME_BLOCK=$'      - type: bind\n        source: '"${MIRA_CODEBASE}"$'/backend\n        target: /MIRA/backend\n      - type: bind\n        source: '"${MIRA_CODEBASE}"$'/frontend\n        target: /MIRA/frontend\n      - type: volume\n        target: /MIRA/frontend/node_modules'
  DEV_ENV_BLOCK=$'    environment:\n      CHOKIDAR_USEPOLLING: "true"\n      WATCHFILES_FORCE_POLLING: "true"'
fi

# If API_PORT is provided, include it in the docker-compose.yml; 
# Otherwise, only expose REACT_PORT
if [[ -n "${API_PORT}" ]]; then
  cat > "${DATA_ROOT}/docker-compose.yml" <<EOF
x-mira-image:
  &mira-image
  ${MIRA_IMAGE}

x-data-storage-path:
  &data-storage-path
  ${DATA_ROOT}

services:
  mira:
    container_name: mira
    image: *mira-image
    networks:
      - mira
    privileged: true
    ports:
      - ${REACT_PORT}:5175
      - ${API_PORT}:8080
    restart: always
    volumes:
      - type: bind
        source: *data-storage-path
        target: /data
${CODEBASE_VOLUME_BLOCK}
    working_dir: /data
${DEV_ENV_BLOCK}

networks:
  mira:
    name: mira
EOF
else
  cat > "${DATA_ROOT}/docker-compose.yml" <<EOF
x-mira-image:
  &mira-image
  ${MIRA_IMAGE}

x-data-storage-path:
  &data-storage-path
  ${DATA_ROOT}

services:
  mira:
    container_name: mira
    image: *mira-image
    networks:
      - mira
    privileged: true
    ports:
      - ${REACT_PORT}:5175
    restart: always
    volumes:
      - type: bind
        source: *data-storage-path
        target: /data
${CODEBASE_VOLUME_BLOCK}
    working_dir: /data
${DEV_ENV_BLOCK}

networks:
  mira:
    name: mira
EOF
fi

# Start Docker containers
echo "Start up the containers. If prompted, enter the admin password to give permissions..."
${SUDO} docker compose -f "${DATA_ROOT}/docker-compose.yml" up -d

# Done
echo ""
echo "MIRA setup is complete!"
echo "MIRA REACT will be deployed at http://localhost:${REACT_PORT}"
if [[ -n "${API_PORT}" ]]; then
  echo "MIRA API will be deployed at http://localhost:${API_PORT}, with interactive docs at http://localhost:${API_PORT}/docs/"
fi
echo ""