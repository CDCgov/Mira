#!/bin/bash 

# Exit immediately if any command fails
set -e

# Get current script directory ####
SCRIPT_DIR="$( realpath $(dirname "${BASH_SOURCE[0]}") )"

# Command-line argument usage
print_usage() {
    cat <<USAGE
Usage: $(basename "$0") --deploy Local --data_dir <DATA_ROOT> --mira_nf_image <MIRA_NF_IMAGE> --host_url <HOST_URL> --host <HOST> --api_port <API_PORT> --react_port <REACT_PORT>

Arguments:
  --deploy <DEPLOY>                 Deployment mode, must be 'Local' or 'Docker'. (Default: Local)
  --data_dir <DATA_ROOT>            Path to the host directory used for MIRA data storage. Must already exist.
  --mira_nf_image <MIRA_NF_IMAGE>   Docker image (name:tag) for the MIRA Nextflow pipeline.
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

# Require all arguments to be provided
if [[ -z "${DEPLOY}" || -z "${DATA_ROOT}" || -z "${MIRA_NF_IMAGE}" || -z "${HOST_URL}" || -z "${HOST}" || -z "${API_PORT}" || -z "${REACT_PORT}" ]]; then
    echo "Invalid arguments." >&2
    usage
fi

echo "Checking deployment..."
if [[ "${DEPLOY}" != "Local" && "${DEPLOY}" != "Docker" ]]; then
    echo "Error: DEPLOY must be either 'Local' or 'Docker', got '${DEPLOY}'." >&2
    exit 1
fi

echo "Checking data storage..."
if [[ ! -d "${DATA_ROOT}" ]]; then
    echo "Error: The data directory '${DATA_ROOT}' does not exist. Please create it before proceeding." >&2
    exit 1
fi

echo "Checking MIRA Nextflow image. If prompted, please enter the admin password to proceed..."
if ! sudo docker inspect "${MIRA_NF_IMAGE}" &> /dev/null; then
    if ! sudo docker pull "${MIRA_NF_IMAGE}" &> /dev/null; then
        echo "Error: Failed to pull MIRA Nextflow image '${MIRA_NF_IMAGE}'." >&2
        exit 1
    fi
fi

# Function to check if a port is available
check_available_port () {
  local port=$1
  local check_port=$(echo -n $(lsof -i:${port}) | wc -m)
  if [ ${check_port} -gt 0 ]
  then
    echo "Error: The requested port ${port} is already in use. Please choose a different port." >&2
    exit 1
  fi
}

# Check if the requested ports are available
check_available_port "${API_PORT}"
check_available_port "${REACT_PORT}"

# Allow 775 permissions for data storage ####
echo "Apply 775 permission to the data storage. If prompted, please enter the admin password to proceed..."
sudo chmod -R 775 "${DATA_ROOT}"

# Run the backend setup scripts in the background so the frontend can start alongside it
bash "${SCRIPT_DIR}/backend/api-kickoff" --deploy "${DEPLOY}" --data_dir "${DATA_ROOT}" --mira_nf_image "${MIRA_NF_IMAGE}" --host_url "${HOST_URL}" --host "${HOST}" --api_port "${API_PORT}" --react_port "${REACT_PORT}" &

# Run the frontend setup scripts in the foreground, keeping this script alive
bash "${SCRIPT_DIR}/frontend/react-kickoff" --host_url "${HOST_URL}" --host "${HOST}" --react_port "${REACT_PORT}" --api_port "${API_PORT}"
