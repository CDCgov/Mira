#!/bin/bash

# Exit immediately if any command fails
set -e

# Command-line argument usage
print_usage() {
    cat <<USAGE
Usage: $(basename "$0") [-h] [--help] --deploy Docker --data_dir <DATA_ROOT> --mira_image <MIRA_IMAGE> [--react_port <REACT_PORT>]

Arguments:
  Required:
  --deploy <DEPLOY>                 Deployment mode, must be 'Docker' for this script. (Default: Docker)
  --data_dir <DATA_ROOT>            Path to host directory to store outputs and logs from MIRA applications.
  --mira_image <MIRA_IMAGE>         Docker image (name:tag) for the MIRA API + REACT application.

  Optional:
  --react_port <REACT_PORT>         Host port to expose MIRA REACT on (Default: 5175). 
                                    If the specified port is in use, an available port will be selected automatically.
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

# Check software requirements before proceeding
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

# Check if Docker Compose (the 'docker compose' plugin, bundled with modern Docker installs) is available
echo "Checking for Docker Compose..."
if ! sudo docker compose version &> /dev/null; then
    echo "Error: Docker Compose plugin is not available. Please update Docker/Docker Desktop to a version that includes 'docker compose'." >&2
    exit 1
fi
echo "Docker Compose: $(sudo docker compose version --short)"

# Check if the MIRA image is available locally, and if not pull it
echo "Checking MIRA image. If prompted, please enter the admin password to proceed..."
if ! sudo docker image inspect "${MIRA_IMAGE}" &> /dev/null; then
    if ! sudo docker pull "${MIRA_IMAGE}" &> /dev/null; then
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
    echo "Port ${port} is in use. Trying port ${new_port}..."
    port=${new_port}
  done
  echo ${port}
}

# Check if the REACT port is available, otherwise find an available port
REACT_PORT=$(find_available_port "${REACT_PORT}")

echo "Configure docker-compose.yml file to initialize the containers..."
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
    working_dir: /data

networks:
  mira:
    name: mira
EOF

# Start Docker containers
echo "Start up the containers. If prompted, enter the admin password to give permissions..."
sudo docker compose -f "${DATA_ROOT}/docker-compose.yml" up -d

# Done
echo ""
echo "MIRA setup is complete!"
echo "MIRA REACT will be deployed at http://localhost:${REACT_PORT}"
echo ""