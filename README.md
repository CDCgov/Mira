
# Requirements

- Docker >= 28.1 (with Docker Compose >= 2.35)

- Python >= 3.13 or Conda >= 25.7 (or micromamba >= 2.0)

- Node.js >= 24 (npm >= 11.11)

# Project Structure

```
MIRA/
├── backend/               # FastAPI backend 
├── fronend/               # React frontend (Vite + Tailwind + shadcn/ui)
└── README.md
```

# Getting Started

## Pull down the MIRA-NF image

```bash
docker pull cdcgov/mira-nf:v2.1.1
```

## Clone the repository and checkout `mira-react` branch

```bash
git clone https://github.com/CDCgov/MIRA.git
cd MIRA
git checkout mira-react
```

## Run `MIRA` locally

## 1. Start the Backend 

### Navigate to the `backend` directory

```bash
cd backend
```

### Create the virtual environment 

Using `venv` + pip (with `requirements.txt`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or using conda/micromamba (with `environment.yml`):

```bash
micromamba env create -n mira_react_env -f environment.yml
micromamba activate mira_react_env
```

> **Note:** If `micromamba activate` fails with `Shell not initialized`, run `micromamba shell init --shell bash --root-prefix=~/micromamba` once, then restart your shell (or `source ~/.bashrc`) before activating.

### Run MIRA backend

With the virtual environment activated, start the FastAPI backend with Uvicorn from the `backend` directory:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080 > mira-backend.log 2>&1 &
```

The API will be available at `http://localhost:8080`, with interactive docs at `http://localhost:8080/docs`.

## 2. Start the Frontend 

### Navigate to the `frontend` directory

```bash
cd frontend
```

### Install React project dependencies

```bash
npm install
```

### Run React app

```bash
npm run dev -- --host 0.0.0.0 --port 5175
```

The React app will be available at `http://localhost:5175`.

## Run `MIRA` via Docker and Compose

### Navigate to `MIRA` main directory

```bash
cd MIRA
```

### Edit `docker-compose-dockerhub.yml` file

- Change `mira-nf-image` to a specific MIRA-NF image that you want to use to run MIRA
- Change `data-storage-path` to a directory on your machine that you would like to store outputs from the app

### Launch MIRA backend and frontend

```bash
docker compose -f docker-compose-dockerhub.yml up -d
```

After deployment ran successfully, 

- The API will be available at `http://localhost:8080`, with interactive docs at `http://localhost:8080/docs`.
- The React app will be available at `http://localhost:5175`.



