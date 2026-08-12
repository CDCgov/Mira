# Create an argument to pull a particular version of micromamba image (backend only)
ARG MICROMAMBA_IMAGE
ARG MICROMAMBA_IMAGE=${MICROMAMBA_IMAGE:-mambaorg/micromamba:2.8.0}

# Define the base image shared by both the backend and frontend stages
ARG UBUNTU_IMAGE
ARG UBUNTU_IMAGE=${UBUNTU_IMAGE:-ubuntu:24.04}

############# micromamba image ##################
FROM ${MICROMAMBA_IMAGE} AS micromamba
RUN echo "Getting micromamba image"

##############################################
#
# BACKEND
#
##############################################

FROM ${UBUNTU_IMAGE} AS backend

ENV MAMBA_ROOT_PREFIX="/opt/conda"
ENV MAMBA_EXE="/bin/micromamba"

COPY --from=micromamba "$MAMBA_EXE" "$MAMBA_EXE"
COPY --from=micromamba /usr/local/bin/_activate_current_env.sh /usr/local/bin/_activate_current_env.sh
COPY --from=micromamba /usr/local/bin/_dockerfile_shell.sh /usr/local/bin/_dockerfile_shell.sh
COPY --from=micromamba /usr/local/bin/_entrypoint.sh /usr/local/bin/_entrypoint.sh
COPY --from=micromamba /usr/local/bin/_dockerfile_initialize_user_accounts.sh /usr/local/bin/_dockerfile_initialize_user_accounts.sh
COPY --from=micromamba /usr/local/bin/_dockerfile_setup_root_prefix.sh /usr/local/bin/_dockerfile_setup_root_prefix.sh

# Install system dependencies
ARG DEBIAN_FRONTEND=noninteractive

# local apt mirror support
# start every stage with updated apt sources
ARG APT_MIRROR_NAME=
RUN if [ -n "$APT_MIRROR_NAME" ]; then sed -i.bak -E '/security/! s^https?://.+?/(debian|ubuntu)^http://'"$APT_MIRROR_NAME"'/\1^' /etc/apt/sources.list && grep '^deb' /etc/apt/sources.list; fi

# Install and update system libraries of general use
RUN apt-get update --allow-releaseinfo-change --fix-missing \
  && apt-get install --no-install-recommends -y \
  ca-certificates \
  git \
  curl \
  dos2unix \
  docker.io \
  && apt clean autoclean \
  && apt autoremove --yes \
  && rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /tmp/* /var/tmp/*

# Default deployment type
ENV DEPLOY=Docker

# Default backend and data directories
ENV BACKEND_DIR=/MIRA-backend
ENV DATA_DIR=/data

# Set up volume directories
VOLUME ${BACKEND_DIR} ${DATA_DIR}

# Set up working directory
WORKDIR ${DATA_DIR}

# Copy all backend scripts to docker image
COPY backend/ ${BACKEND_DIR}

############# Set up certs ##################
# bundle-ca.pem is the CDC-G2 root + CDC-G2-ZSH (Zscaler TLS-inspection) chain
COPY bundle-ca.pem /usr/local/share/ca-certificates/cdc-zscaler-bundle.crt
RUN update-ca-certificates

# Point OpenSSL/pip/requests at the system store instead of certifi's bundled CAs
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

############# Set up micromamba environment ##################

# Copy environment file to docker image
COPY environment.yml ${BACKEND_DIR}/environment.yml

# Create the conda environment from environment.yml
RUN micromamba install --yes --name base -f ${BACKEND_DIR}/environment.yml \
  && micromamba clean --all --yes

############# Launch MIRA Backend ##################

# Copy all files to docker images
COPY backend/api-kickoff ${BACKEND_DIR}/api-kickoff

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${BACKEND_DIR}/api-kickoff

# Allow permission to execute the bash scripts
RUN chmod a+x ${BACKEND_DIR}/api-kickoff

# Activate conda environment on PATH
ENV PATH="$PATH:${MAMBA_ROOT_PREFIX}/bin"

# Make the app available at port 8080
EXPOSE 8080

# Execute the pipeline
ENTRYPOINT ["/bin/bash", "-c", "uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8080"]

##############################################
#
# FRONTEND
#
##############################################

FROM ${UBUNTU_IMAGE} AS frontend

############# Install baseline packages ##################
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update --allow-releaseinfo-change --fix-missing \
  && apt-get install --no-install-recommends -y \
  ca-certificates \
  curl \
  gnupg \
  dos2unix \
  && apt clean autoclean \
  && apt autoremove --yes \
  && rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /tmp/* /var/tmp/*

############# Set up certs ##################

# bundle-ca.pem is the CDC-G2 root + CDC-G2-ZSH (Zscaler TLS-inspection) chain — must be
# trusted before the NodeSource repo (HTTPS) can be reached below.
COPY bundle-ca.pem /usr/local/share/ca-certificates/cdc-zscaler-bundle.crt
RUN update-ca-certificates

# Point OpenSSL/pip/requests at the system store instead of certifi's bundled CAs
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

############# Install Node.js (version set via NODE_VERSION build arg) ##################

# Ubuntu 24.04's own apt repos ship an older Node.js, so pull from NodeSource instead
# Define node.js version to install for the frontend stage
ARG NODE_VERSION
ARG NODE_VERSION=${NODE_VERSION:-24}
RUN mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
  && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_VERSION}.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
  && apt-get update \
  && apt-get install --no-install-recommends -y nodejs \
  && apt clean autoclean \
  && apt autoremove --yes \
  && rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /tmp/* /var/tmp/*

# Create a program variable
ENV DASHBOARD_DIR=/MIRA-frontend

# Set up volume directory
VOLUME ${DASHBOARD_DIR}

# Set up working directory
WORKDIR ${DASHBOARD_DIR}

# Copy source code
COPY frontend/ ${DASHBOARD_DIR}

############# Launch REACT Backend ##################

# Copy all files to docker images
COPY frontend/react-kickoff ${DASHBOARD_DIR}/react-kickoff

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${DASHBOARD_DIR}/react-kickoff

# Allow permission to execute the bash scripts
RUN chmod a+x ${DASHBOARD_DIR}/react-kickoff

# Expose app to port 5175
EXPOSE 5175

# Install dependencies listed in package-lock.json and clean npm cache
RUN npm ci && npm cache clean --force

# Start the Vite dev server
ENTRYPOINT ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5175"]
