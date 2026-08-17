
# MIRA

MIRA combines a FastAPI backend, a React frontend, and the MIRA Nextflow pipeline to process sequencing runs for influenza, SARS-CoV-2, and RSV.

There are two types of deployment to run this pipeline:

- **Local:** Run FastAPI and React on the host and launch MIRA-NF through Docker.
- **Docker + Compose:** Run FastAPI, React, and MIRA-NF from one combined application container.

## Project Structure

```
MIRA/
├── backend/                    # FastAPI application
├── frontend/                   # React/Vite application
├── Dockerfile                  # Combined application image
├── docker-entrypoint.sh        # Starts FastAPI and React in the container
├── docker-compose.yml          # Local image deployment
├── docker-compose-dev.yml      # Development deployment with source mounts
├── docker-compose-ghcr.yml     # Published GHCR image deployment
├── kickoff_mira_local.sh       # Local backend and frontend deployment
├── kickoff_mira_docker.sh      # Docker + Compose deployment
└── README.md
```

## Before you begin

Create a persistent data directory for uploaded files, SQLite state, logs, and pipeline outputs:

```bash
mkdir -p ${HOME}/FLU_SC2_SEQUENCING
```

## Local deployment

Use `kickoff_mira_local.sh` to run FastAPI with Uvicorn and React with Vite on the host. The launcher will verify and install required dependencies, create a Micromamba environment defined by `environment.yml`, and configure owner permissions for the data directory.

```bash
bash kickoff_mira_local.sh \
	--deploy Local \
	--data_dir <DATA_ROOT> \
	--mira_nf_image <MIRA_NF_IMAGE> \
	[--react_port <REACT_PORT>] \
	[--api_port <API_PORT>]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--deploy` | Yes | `Local` | Deployment mode. This launcher accepts only `Local`. |
| `--data_dir` | Yes | - | Existing host directory used for MIRA data, logs, and SQLite state. |
| `--mira_nf_image` | Yes | - | MIRA Nextflow Docker image in `name:tag` format. |
| `--react_port` | No | `5175` | React frontend port. |
| `--api_port` | No | `8080` | Backend API port. |
| `-h` or `--help` | No | - | Print usage and exit. |

Example:

```bash
bash kickoff_mira_local.sh \
    --deploy Local \
	--data_dir ${HOME}/FLU_SC2_SEQUENCING \
	--mira_nf_image cdcgov/mira-nf:v2.2.1 \
	--api_port 8080 \
	--react_port 5175
```

The launcher installs or verifies Micromamba, Docker, Docker Compose, Node.js, and the Python environment. It terminates process groups recorded by a previous launch, selects another port when a requested port is occupied, and starts both applications detached. Runtime files are stored under `<DATA_ROOT>/logs/`:

- `api-kickoff.log`     - FastAPI/Uvicorn output
- `react-kickoff.log`   - React Vite output
- `pid.log`             - process-group IDs for the running backend and frontend

To stop a local deployment, run:

```bash
while read -r pid; do
	kill -- "-${pid}"
done < ${HOME}/FLU_SC2_SEQUENCING/logs/pid.log
```

## Docker + Compose deployment

Use `kickoff_mira_docker.sh` to generate a Compose configuration in the data directory and start the combined `mira` service in detached mode. The launcher verifies Docker and Docker Compose, pulls the requested application image when necessary, and starts the service with `privileged: true` so MIRA-NF can launch nested Singularity sandboxes.

```bash
bash kickoff_mira_docker.sh \
	--deploy Docker \
	--data_dir <DATA_ROOT> \
	--mira_image <MIRA_IMAGE> \
	[--react_port <REACT_PORT>] \
	[--api_port <API_PORT>]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--deploy` | Yes | `Docker` | Deployment mode. This launcher accepts only `Docker`. |
| `--data_dir` | Yes | - | Existing host directory used for MIRA data, logs, and the generated Compose file. |
| `--mira_image` | Yes | - | Combined MIRA API, React, and pipeline image in `name:tag` format. |
| `--react_port` | No | `5175` | Host port that exposes the React frontend. |
| `--api_port` | No | Not published | Optional host port that exposes the backend API directly. React continues to access it through `/api`. |
| `-h` or `--help` | No | - | Print usage and exit. |

Example:

```bash
bash kickoff_mira_docker.sh \
    --deploy Docker \
    --data_dir ${HOME}/FLU_SC2_SEQUENCING \
	--mira_image ghcr.io/rchau88/mira:latest \
	--react_port 5175 \
	--api_port 8080
```

The generated Compose configuration is saved to `<DATA_ROOT>/docker-compose.yml`. Container logs are written to `<DATA_ROOT>/logs/api-kickoff.log` and `<DATA_ROOT>/logs/react-kickoff.log`.

To inspect the services:

```bash
docker compose -f ${HOME}/FLU_SC2_SEQUENCING/docker-compose.yml ps
```

To stop and remove the application containers:

```bash
docker compose -f ${HOME}/FLU_SC2_SEQUENCING/docker-compose.yml down
```

## Access the applications

After deployment, open the URLs printed by the launcher. The React application sends backend requests through its same-origin `/api` proxy.

- React application: `http://localhost:<REACT_PORT>`
- API documentation when `--api_port` is published: `http://localhost:<API_PORT>/docs`

Example output:
```bash
...
MIRA setup is complete!
MIRA REACT will be deployed at http://localhost:5175
MIRA API will be deployed at http://localhost:8080, with interactive docs at http://localhost:8080/docs/
```
