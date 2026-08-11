
# Requirements

- Git >= 2.25

- Docker >= 28.1 (with Docker Compose >= 2.35)

- Node.js >= 24

- Micromamba >= 2.0


# Project Structure

```
MIRA/
├── backend/               # FastAPI backend 
├── frontend/              # React frontend (Vite + Tailwind + shadcn/ui)
└── README.md
```

# Getting Started

## Check version of Docker and Compose 

```bash
docker --version
docker compose --version
```

## Check version of `node.js`

```bash
node --version
```

## Pull down MIRA-NF image

```bash
docker pull cdcgov/mira-nf:v2.2.0
```

## Run `MIRA` locally

Here we recommend using micromamba to set up a virtual environment to run `MIRA` locally. **Micromamba** is a tiny, statically linked C++ reimplementation of mamba which is an alternative to conda. The tool works as a standalone package manager that supports a subset of all mamba or conda commands, but it also has its own separate command line interfaces. For more information, visit [micromamba documentation](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html).

To install, download and unzip the executable from the official conda-forge package to your `$HOME` directory.

```bash
cd $HOME
```

LINUX
```bash
# Linux Intel (x86_64):
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
# Linux ARM64:
curl -Ls https://micro.mamba.pm/api/micromamba/linux-aarch64/latest | tar -xvj bin/micromamba
# Linux Power:
curl -Ls https://micro.mamba.pm/api/micromamba/linux-ppc64le/latest | tar -xvj bin/micromamba
```

macOS
```bash
# macOS Intel (x86_64):
curl -Ls https://micro.mamba.pm/api/micromamba/osx-64/latest | tar -xvj bin/micromamba
# macOS Silicon/M1 (ARM64):
curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xvj bin/micromamba
```

After the extraction is completed, you can find the executable at `$HOME/bin/micromamba`

To quickly use micromamba, you can simply run
```bash
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
eval "$($HOME/bin/micromamba shell hook -s posix)"
```

To persist using micromamba, you can append the following script to your `.bashrc` (or `.zshrc`)

```bash
# >>> mamba initialize >>>
export MAMBA_EXE="$HOME/bin/micromamba";
export MAMBA_ROOT_PREFIX="$HOME/micromamba";
__mamba_setup="$("$MAMBA_EXE" shell hook --shell bash --root-prefix "$MAMBA_ROOT_PREFIX" 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__mamba_setup"
else
    alias micromamba="$MAMBA_EXE"  # Fallback on help from mamba activate
fi
unset __mamba_setup
# <<< mamba initialize <<<
```

To check the version of micromamba
```bash
micromamba --version
```

### Set up a micromamba environment

- Clone this repository to your `$HOME` directory

```bash
git clone https://github.com/CDCgov/MIRA.git
cd MIRA
git checkout mira-react
```

- Navigate to `MIRA` folder where the `environment.yml` file is stored. Let’s create a virtual environment named `mira_react_env` that contains all dependencies needed to run MIRA.

```bash
micromamba env create -n mira_react_env -f environment.yml
```

- Activate the environment
```bash
micromamba activate mira_react_env
```

### 1. Run MIRA backend

- Navigate to the `backend` directory

```bash
cd backend
```

- With the virtual environment activated, start the FastAPI backend using the `api-kickoff` bash script from the `backend` directory. This generates the `config.yml` to be used by the app and then launches the Swagger API.

```bash
./api-kickoff \
    --deploy Local \
    --data_dir /path/to/data \
    --mira_nf_image cdcgov/mira-nf:v2.2.0 \
    --host_url localhost \
    --host 0.0.0.0 \
    --api_port 8080 \
    --react_port 5175 > mira-backend.log 2>&1 &
```

- `--deploy` Options: Local or Docker. Must be `Local` for this workflow.
- `--data_dir` is the directory on your machine used to store outputs from the app. **IMPORTANT**: Make sure the data directory has `rwx` or `775` permissions.
- `--mira_nf_image` is the MIRA-NF Docker image to be used to run genome assembly. See [Pull down MIRA-NF image](#pull-down-mira-nf-image).
- `--host_url` is the hostname used to build the API and React URLs. (default: `localhost`)
- `--host` is the address uvicorn binds to. (default: `0.0.0.0`)
- `--api_port` is the port uvicorn serves the backend API on. (default: `8080`)
- `--react_port` is the port where React is deployed at. (default: `5175`)

The API will be available at `http://localhost:8080`, with interactive docs at `http://localhost:8080/docs`.

### 2. Start the Frontend 

- Navigate to the `frontend` directory

```bash
cd frontend
```

- Install project dependencies an launch app

```bash
./react-kickoff \
    --host_url localhost \
    --host 0.0.0.0 \
    --api_port 8080 \
    --react_port 5175 
```

- `--host_url` is the hostname used to build the API and React URLs. (default: `localhost`)
- `--host` is the address uvicorn binds to. (default: `0.0.0.0`)
- `--api_port` is the port uvicorn serves the backend API on. (default: `8080`)
- `--react_port` is the port where React is deployed at. (default: `5175`)

The React app will be available at `http://localhost:5175`.

## Run `MIRA` via Docker and Compose

- Navigate to `MIRA` main directory

```bash
cd MIRA
```

- Edit `docker-compose-dockerhub.yml` file

    - Change `mira-nf-image` to a specific MIRA-NF image that you want to use to run MIRA. See [Pull down MIRA-NF image](#pull-down-mira-nf-image).
    - Change `data-storage-path` to a directory on your machine that you would like to store outputs from the app. **IMPORTANT**: Make sure the data directory has `rwx` or `775` permissions.

- Launch MIRA backend and frontend

```bash
docker compose -f docker-compose-dockerhub.yml up -d
```

After deployment ran successfully, 

- The API will be available at `http://localhost:8080`, with interactive docs at `http://localhost:8080/docs`.
- The React app will be available at `http://localhost:5175`.
