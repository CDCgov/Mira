
# Create an argument to pull a particular version of micromamba image
ARG MICROMAMBA_IMAGE
ARG MICROMAMBA_IMAGE=${MICROMAMBA_IMAGE:-mambaorg/micromamba:2.8.0}

# Define the base image for the Dockerfile
ARG UBUNTU_IMAGE
ARG UBUNTU_IMAGE=${UBUNTU_IMAGE:-ubuntu:26.04}

############# micromamba image ##################
FROM ${MICROMAMBA_IMAGE} as micromamba
RUN echo "Getting micromamba image"

############# base image ##################

FROM ${UBUNTU_IMAGE} as base

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
  && rm -rf /var/lib/{apt,dpkg,cache,log}/*

# Required certs to download conda packages
COPY ca.crt /usr/local/share/ca-certificates/ca.crt
RUN update-ca-certificates

# Create a program variable
ENV BACKEND_DIR=/MIRA-backend

# Set up volume directory 
VOLUME ${BACKEND_DIR}

# Set up working directory 
WORKDIR ${BACKEND_DIR}

# Copy all scripts to docker images
COPY . ${BACKEND_DIR}

############# Set up micromamba environment ##################

# Copy environment file to docker image
COPY environment.yml ${BACKEND_DIR}/environment.yml

# Create the conda environment from environment.yml
RUN micromamba install --yes --name base -f ${BACKEND_DIR}/environment.yml \
  && micromamba clean --all --yes

############# Launch MIRA Backend ##################

# Copy all files to docker images
COPY api-kickoff ${BACKEND_DIR}/api-kickoff

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${BACKEND_DIR}/api-kickoff

# Allow permission to execute the bash scripts
RUN chmod a+x ${BACKEND_DIR}/api-kickoff

# Activate conda environment on PATH
ENV PATH="$PATH:${MAMBA_ROOT_PREFIX}/bin"

# Make the app available at port 8080
EXPOSE 8080

# Execute the pipeline 
ENTRYPOINT ["/bin/bash", "-c", "${BACKEND_DIR}/api-kickoff"]

