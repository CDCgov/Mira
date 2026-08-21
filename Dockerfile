# Create an argument to pull a particular version of micromamba image (backend only)
ARG MICROMAMBA_IMAGE
ARG MICROMAMBA_IMAGE=${MICROMAMBA_IMAGE:-mambaorg/micromamba:2.8.0}

# Define the base image shared by both the backend and frontend stages
ARG MIRA_NF_IMAGE
ARG MIRA_NF_IMAGE=${MIRA_NF_IMAGE:-cdcgov/mira-nf:v2.2.1}

############# MICROMAMBA IMAGE ##################
FROM ${MICROMAMBA_IMAGE} AS micromamba
RUN echo "Getting micromamba image"

############# MIRA IMAGE ##################
FROM ${MIRA_NF_IMAGE} AS base

ARG MIRA_NF_IMAGE
ENV MIRA_NF_IMAGE="${MIRA_NF_IMAGE}"

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
  lsof \
  gnupg \
  dos2unix \
  && apt clean autoclean \
  && apt autoremove --yes \
  && rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /tmp/* /var/tmp/*

################# Set up certs ##############################

# bundle-ca.pem is the CDC-G2 root + CDC-G2-ZSH (Zscaler TLS-inspection) chain
COPY bundle-ca.pem /usr/local/share/ca-certificates/cdc-zscaler-bundle.crt
RUN update-ca-certificates

# Point OpenSSL/pip/requests at the system store instead of certifi's bundled CAs
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt  

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

# Default backend and data directories
ENV MIRA_DIR=/MIRA
ENV FRONTEND_DIR=${MIRA_DIR}/frontend
ENV BACKEND_DIR=${MIRA_DIR}/backend
ENV DATA_DIR=/data

# Set up the data volume. Do NOT declare the code dirs as VOLUMEs: that spawns anonymous
# volumes that shadow a bind-mounted /MIRA and hide live code edits during development.
VOLUME ${DATA_DIR}

############# MIRA DESCRIPTION ##################

COPY DESCRIPTION ${MIRA_DIR}/DESCRIPTION

############# MIRA Backend ##################

# Copy all backend scripts to docker image
COPY backend/ ${BACKEND_DIR}

# Copy environment file to docker image
COPY environment.yml ${BACKEND_DIR}/environment.yml

# Create the conda environment from environment.yml
RUN micromamba install --yes --name base -f ${BACKEND_DIR}/environment.yml \
  && micromamba clean --all --yes

# Stock polars ships AVX-optimized wheels that SIGSEGV under x86-64 emulation (e.g. the
# amd64 image run via Rosetta on Apple Silicon) during pandera validation. Set
# POLARS_PACKAGE to the AVX-free build (e.g. "polars-lts-cpu==1.33.1") to swap it in;
# empty (the default) keeps the stock wheel so native x86-64 builds are unaffected.
# polars-lts-cpu ships the same "polars" module, so the stock wheel is removed first to
# avoid a mixed install.
ARG POLARS_PACKAGE=
RUN if [ -n "$POLARS_PACKAGE" ]; then \
      "${MAMBA_ROOT_PREFIX}/bin/pip" uninstall -y polars polars-lts-cpu >/dev/null 2>&1 || true; \
      "${MAMBA_ROOT_PREFIX}/bin/pip" install --no-cache-dir "$POLARS_PACKAGE"; \
    fi

# Activate conda environment on PATH
ENV PATH="$PATH:${MAMBA_ROOT_PREFIX}/bin"

# Copy bash script to docker image
COPY backend/api-kickoff ${BACKEND_DIR}/api-kickoff

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${BACKEND_DIR}/api-kickoff

# Allow permission to execute the bash script
RUN chmod a+x ${BACKEND_DIR}/api-kickoff

############# MIRA frontend ##################

# Copy source code
COPY frontend/ ${FRONTEND_DIR}

# Copy all files to docker images
COPY frontend/react-kickoff ${FRONTEND_DIR}/react-kickoff

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${FRONTEND_DIR}/react-kickoff

# Allow permission to execute the bash script
RUN chmod a+x ${FRONTEND_DIR}/react-kickoff

# Set working directory to the frontend directory
WORKDIR ${FRONTEND_DIR}

# Install dependencies listed in package-lock.json and clean npm cache
RUN npm ci && npm cache clean --force

############# Launch MIRA ##################

# Expose backend app to port 8080 and frontend app to port 5175
EXPOSE 8080 5175

# Set working directory to data directory 
WORKDIR ${DATA_DIR}

# Copy entrypoint script to docker image
COPY docker-entrypoint.sh ${MIRA_DIR}/docker-entrypoint.sh

# Allow permission to execute the bash script
RUN chmod a+x ${MIRA_DIR}/docker-entrypoint.sh

# Set entrypoint to launch both backend and frontend applications
ENTRYPOINT ["/bin/bash", "-c", "exec ${MIRA_DIR}/docker-entrypoint.sh --deploy Docker --data_dir \"${DATA_DIR}\" --mira_nf_image \"${MIRA_NF_IMAGE}\" --react_port 5175 --api_port 8080"]