
# MIRA

MIRA combines a FastAPI backend, a React frontend, and a MIRA Nextflow pipeline to process sequencing runs for FLU, SARS-COV-2, and RSV.

There are two types of deployment to run this pipeline:

- **Local:** Run the backend and frontend on the host, and the Nextflow pipeline runs in Docker.
- **Docker + Compose:** Run the full application stack in containers.

## Project Structure

```
MIRA/
├── backend/                    # FastAPI application
├── frontend/                   # React/Vite application
├── kickoff_mira_local.sh       # Local backend and frontend deployment
├── kickoff_mira_docker.sh      # Docker + Compose deployment
└── README.md
```

## Before you begin

Create a data source in your $HOME directory where you would store the outputs of the MIRA applications

Example
```bash
mkdir -p ${HOME}/FLU_SC2_SEQUENCING
```

## Local deployment

Use `kickoff_mira_local.sh` to run FastAPI with Uvicorn and React with Vite on the host. The launcher will verify and install required dependencies, create a Micromamba environment defined by `environment.yml`, and configure owner permissions for the data directory.

```bash
bash kickoff_mira_local.sh [-h] [--help] --deploy Local --data_dir <DATA_ROOT> --mira_nf_image <MIRA_NF_IMAGE> --host_url <HOST_URL> --host <HOST> --api_port <API_PORT> --react_port <REACT_PORT>
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `-h` or `--help` | No | - | Print usage and exit. |
| `--deploy` | yes | `Local` | Deployment mode. This launcher accepts only `Local`. |
| `--data_dir` | Yes | - | Existing host directory used for MIRA data, logs, and SQLite state. |
| `--mira_nf_image` | Yes | - | MIRA Nextflow Docker image in `name:tag` format. |
| `--host_url` | No | `localhost` | Hostname used to launch the applications. |
| `--host` | No | `0.0.0.0` | Bind address for the backend and frontend servers. |
| `--api_port` | No | `8080` | Backend API port. |
| `--react_port` | No | `5175` | React frontend port. |

Example:

```bash
bash kickoff_mira_local.sh \
    --deploy Local \
	--data_dir ${HOME}/FLU_SC2_SEQUENCING \
	--mira_nf_image cdcgov/mira-nf:v2.2.0
```

The launcher starts both applications in the background. If a requested port is unavailable, it selects an available port. Runtime log files are stored in `${HOME}/FLU_SC2_SEQUENCING/logs/`:

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

Use `kickoff_mira_docker.sh` to generate a Compose configuration in the data directory and start the `mira-nf`, `mira-backend`, and `mira-frontend` services in detached mode. The launcher verifies or installs Docker and Docker Compose when needed.

```bash
bash kickoff_mira_docker.sh [-h] [--help] --deploy Docker --data_dir <DATA_ROOT> --mira_nf_image <MIRA_NF_IMAGE> --host_url <HOST_URL> --host <HOST> --api_port <API_PORT> --react_port <REACT_PORT>
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `-h` or `--help` | No | - | Print usage and exit. |
| `--deploy` | Yes | `Docker` | Deployment mode. This launcher accepts only `Docker`. |
| `--data_dir` | Yes | - | Existing host directory used for MIRA data, logs, and the generated Compose file. |
| `--mira_nf_image` | Yes | - | MIRA Nextflow Docker image in `name:tag` format. |
| `--host_url` | No | `localhost` | Hostname used in URLs printed after startup. |
| `--host` | No | `0.0.0.0` | Bind address used within the containers. |
| `--api_port` | No | `8080` | Host port that exposes the backend API. |
| `--react_port` | No| `5175` | Host port that exposes the React frontend. |

Example:

```bash
bash kickoff_mira_docker.sh \
    --deploy Docker \
    --data_dir ${HOME}/FLU_SC2_SEQUENCING \
	--mira_nf_image cdcgov/mira-nf:v2.2.0
```

The generated Compose configuration is saved to `${HOME}/FLU_SC2_SEQUENCING/docker-compose.yml`. Container logs are written to `${HOME}/FLU_SC2_SEQUENCING/logs/api-kickoff.log` and `${HOME}/FLU_SC2_SEQUENCING/logs/react-kickoff.log`.

To inspect the services:

```bash
docker compose -f ${HOME}/FLU_SC2_SEQUENCING/docker-compose.yml ps
```

To stop and remove the application containers:

```bash
docker compose -f ${HOME}/FLU_SC2_SEQUENCING/docker-compose.yml down
```

## Access the applications

After deployment, open the URLs printed by the launcher:

- React application: `http://<HOST_URL>:<REACT_PORT>`
- API documentation: `http://<HOST_URL>:<API_PORT>/docs`

Example output:
```bash
...
MIRA setup is complete!
MIRA API will be deployed at http://localhost:8080, with interactive docs at http://localhost:8080/docs/
MIRA REACT will be deployed at http://localhost:5175
```
