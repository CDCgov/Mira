#!/bin/bash

# Exit immediately if any command fails
set -e

# Get current script directory ####
SCRIPT_DIR="$( realpath $(dirname "${BASH_SOURCE[0]}") )"

# Command-line argument usage
print_usage() {
    cat <<USAGE
Usage: $(basename "$0") [-h] [--help] --deploy Docker --data_dir <DATA_ROOT> --mira_nf_image <MIRA_NF_IMAGE> [--host_url <HOST_URL>] [--host <HOST>] [--api_port <API_PORT>] [--react_port <REACT_PORT>]

Arguments:
  Required:
  --deploy <DEPLOY>                 Deployment mode, must be 'Docker' for this script. (Default: Docker)
  --data_dir <DATA_ROOT>            Path to the host directory used for MIRA data storage. Must already exist.
  --mira_nf_image <MIRA_NF_IMAGE>   Docker image (name:tag) for the MIRA Nextflow pipeline.
  
  Optional:
  --host_url <HOST_URL>             Hostname used to build the URLs printed after startup. (Default: localhost)
  --host <HOST>                     Address the backend/frontend servers bind to inside their containers. (Default: 0.0.0.0)
  --api_port <API_PORT>             Host port to expose the MIRA backend API on. (Default: 8080)
  --react_port <REACT_PORT>         Host port to expose the MIRA React frontend on. (Default: 5175)
  -h, --help                        Show this help message and exit.
USAGE
}

usage() {
    print_usage >&2
    exit 1
}

# Initialize deployment variables
DEPLOY="Docker"
DATA_ROOT=""
MIRA_NF_IMAGE=""
MIRA_BACKEND_IMAGE="rchau88/mira-backend:latest"  
MIRA_FRONTEND_IMAGE="rchau88/mira-frontend:latest"

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
if [[ "${DEPLOY}" != "Docker" ]]; then
    echo "Error: DEPLOY must be 'Docker' for this script, got '${DEPLOY}'." >&2
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

# Check software requirements before proceeding
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

echo "Configure docker-compose.yml file to initialize the containers..."
cat > "${DATA_ROOT}/docker-compose.yml" <<EOF
x-mira-nf-image:
  &mira-nf-image
  ${MIRA_NF_IMAGE}

x-data-storage-path:
  &data-storage-path
  ${DATA_ROOT}

services:
  mira-nf:
    container_name: mira-nf
    image: *mira-nf-image
    networks:
      - mira-react
    restart: always
    command: ["tail", "-f", "/dev/null"]  

  mira-backend:
    container_name: mira-backend
    image: ${MIRA_BACKEND_IMAGE}
    depends_on:
      - mira-nf
    networks:
      - mira-react
    ports:
      - ${API_PORT}:${API_PORT}
    restart: always
    environment:
      HOST_MIRA_NF_IMAGE: *mira-nf-image
      HOST_DATA_STORAGE_PATH: *data-storage-path
    volumes:
      - type: bind
        source: *data-storage-path
        target: /data
      - /var/run/docker.sock:/var/run/docker.sock
    working_dir: /data
    entrypoint: ["/bin/bash", "-c", "/MIRA-backend/api-kickoff --deploy Docker --data_dir /data --mira_nf_image \"\$\$HOST_MIRA_NF_IMAGE\" --host_url ${HOST_URL} --host ${HOST} --api_port ${API_PORT} --react_port ${REACT_PORT}"]

  mira-frontend:
    container_name: mira-frontend
    image: ${MIRA_FRONTEND_IMAGE}
    depends_on:
      - mira-nf
      - mira-backend
    networks:
      - mira-react    
    ports:
      - ${REACT_PORT}:${REACT_PORT}
    restart: always
    working_dir: /MIRA-frontend
    entrypoint: ["/bin/sh", "-c", "/MIRA-frontend/react-kickoff --host_url ${HOST_URL} --host ${HOST} --react_port ${REACT_PORT} --api_port ${API_PORT}"]

networks:
  mira-react:
    name: mira-react
EOF

# Start Docker containers
echo "Start up the containers. If prompted, enter the admin password to give permissions..."
sudo docker compose -f ${DATA_ROOT}/docker-compose.yml up -d

# Done
echo ""
echo "MIRA setup is complete!"
echo "MIRA REACT will be deployed at http://localhost:${REACT_PORT}"
echo "MIRA API will be deployed at http://localhost:${API_PORT}, with interactive docs at http://localhost:${API_PORT}/docs/"
echo ""