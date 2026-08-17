
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
├── kickoff_mira_local.sh       # Local backend and frontend deployment
├── kickoff_mira_docker.sh      # Docker + Compose deployment
└── README.md
```

## Before you begin

- Create a persistent data storage for storing uploaded files, SQLite state, app logs, and pipeline outputs.

For example, create `FLU_SC2_SEQUENCING` data storage in your `$HOME` directory

```bash
mkdir -p ${HOME}/FLU_SC2_SEQUENCING
```

- Git pull this repo to your `$HOME` directory and checkout `mira-react` branch

```bash
cd $HOME
git clone https://github.com/CDCgov/Mira.git
cd Mira
git checkout mira-react
```

## Local deployment

Use `kickoff_mira_local.sh` to run FastAPI with Uvicorn and React with Vite on the host. The launcher will verify and install required dependencies, create a Micromamba environment defined by `environment.yml`, and configure access permissions to your data directory before launching the applications in detached mode.

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
| `--data_dir` | Yes | - | Existing host directory for storing MIRA data, logs, and SQLite state. |
| `--mira_nf_image` | Yes | - | MIRA Nextflow Docker image in `name:tag` format. |
| `--react_port` | No | `5175` | Host port to deploy MIRA REACT on. If the specified port is in use, an available port will be selected automatically. |
| `--api_port` | No | `8080` | Host port to deploy MIRA API on. If the specified port is in use, an available port will be selected automatically. |
| `-h` or `--help` | No | - | Print usage and exit. |

Example:

```bash
bash kickoff_mira_local.sh \
    --deploy Local \
	--data_dir ${HOME}/FLU_SC2_SEQUENCING \
	--mira_nf_image cdcgov/mira-nf:v2.2.1 \
	--react_port 5175 \
	--api_port 8080
```

The launcher installs or verifies Micromamba, Docker, Node.js, and the Python environment before launching the applications in detached mode. Runtime log files are stored under `${HOME}/FLU_SC2_SEQUENCING/logs/`:

- `api-kickoff.log`     - FastAPI/Uvicorn output
- `react-kickoff.log`   - React Vite output
- `pid.log`             - process-group IDs for the running backend and frontend

To stop a local deployment, run:

```bash
while read -r pid; do
	kill -- "-${pid}"
done < ${HOME}/FLU_SC2_SEQUENCING/logs/pid.log

To find and kill the deployed ports instead, run:

```bash
for port in 5175 8080; do
	while read -r pid; do
		kill -- "-${pid}" 2>/dev/null || kill "${pid}"
	done < <(lsof -tiTCP:"${port}" -sTCP:LISTEN)
done
```

## Docker + Compose deployment

Use `kickoff_mira_docker.sh` to generate a Compose configuration in the data directory and start the `mira` service in detached mode.

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
| `--data_dir` | Yes | - | Existing host directory for storing MIRA data, logs, SQLite state, and the generated Compose file. |
| `--mira_image` | Yes | - | MIRA Docker image in `name:tag` format. |
| `--react_port` | Yes | `5175` | Host port to expose MIRA REACT on. |
| `--api_port` | No | - | Host port to deploy MIRA API on. If provided, backend API will be exposed to host |
| `-h` or `--help` | No | - | Print usage and exit. |

Example:

```bash
bash kickoff_mira_docker.sh \
    --deploy Docker \
    --data_dir ${HOME}/FLU_SC2_SEQUENCING \
	--mira_image ghcr.io/rchau88/mira:latest \
	--react_port 5175
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

After deployment, the URLs of the applications will be printed by the launcher. 

- React application: `http://localhost:<REACT_PORT>`
- API documentation when `--api_port` is published: `http://localhost:<API_PORT>/docs`

Example output:
```bash
...
MIRA setup is complete!
MIRA REACT will be deployed at http://localhost:5175
MIRA API will be deployed at http://localhost:8080, with interactive docs at http://localhost:8080/docs/
```
