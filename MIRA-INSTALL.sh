#!/bin/bash

[ "$(whoami)" != 'root' ] && echo -e "\nPlease run with sudo:\n\n\tsudo $0\n" && exit

echo -e "\n\n\tYour individual sequencing runs must be saved inside ${PWD}\n\
    \tEnter \"yes\" to confirm.\n\n\
    \tEnter anything else to change the folder to save your\n\
    \tindividual sequencing run folders into and change directory (cd) \
    \n\tinto that folder and rerun this script.\n\n"

read -r RESPONSE

[ "${RESPONSE,,}" != "yes" ] && exit

# Add google as domain name server
grep 8.8.8.8 /etc/resolv.conf >/dev/null || echo nameserver 8.8.8.8 >> /etc/resolv.conf

# Update apt-get
if [[ "$(uname)" != 'Darwin' ]]; then
  apt-get update
  apt-get install docker
fi
# Remove pre-MIRA software
for i in $(docker ps |tr -s ' ' |cut -d ' ' -f2 | grep -e irma-spy -e sc2-spike-seq -e ispy); do
  docker stop "$i"
  docker rm -f "$i"
  docker rmi -f "$i"
done

# MIRA
export COMPOSE_PROJECT_NAME=mira

DC_FILE_CONTENT="version: \"3.9\"\n\
\n\
x-dais-version:\n\
  &dais-version \n\
  public.ecr.aws/n3z8t4o2/dais-ribosome:1.2.1\n\
\n\
x-irma-version:\n\
  &irma-version \n\
  public.ecr.aws/n3z8t4o2/irma:1.0.2p3\n\
\n\
x-spyne-git-version:\n\
  &spyne-git-version  \n\
  https://github.com/cdcgov/spyne.git#prod\n\
\n\
x-mira-git-version:\n\
  &mira-git-version  \n\
  https://github.com/CDCgov/MIRA.git#prod \n\
\n\
x-data-volumes:\n\
  &data-volume\n\
  type: bind\n\
  source: ${PWD}\n\
  target: /data\n\
\n\
x-docker-volumes:\n\
  &docker-socket\n\
  type: bind\n\
  source: /var/run/docker.sock \n\
  target: /var/run/docker.sock \n\
\n\
services:\n\
  dais: \n\
    container_name: dais\n\
    image: *dais-version\n\
    networks:\n\
      - backend\n\
    volumes: \n\
      - *data-volume\n\
    command: tail -f /dev/null\n\
\n\
  irma: \n\
    container_name: irma\n\
    image: *irma-version\n\
    restart: always\n\
    networks:\n\
      - backend\n\
    volumes:\n\
      - *data-volume\n\
    command: tail -f /dev/null\n\
\n\
  spyne: \n\
    container_name: spyne\n\
    image: spyne\n\
    build: \n\
      context: *spyne-git-version \n\
    depends_on:\n\
      - dais\n\
      - irma\n\
    restart: always\n\
    networks:\n\
      - backend\n\
    volumes:\n\
      - *data-volume\n\
      - *docker-socket\n\
    command: tail -f /dev/null\n\
\n\
  mira: \n\
    container_name: mira\n\
    image: mira\n\
    build: \n\
      context: *mira-git-version  \n\
    depends_on:\n\
      - dais\n\
      - irma\n\
      - spyne\n\
    restart: always\n\
    networks:\n\
      - frontend\n\
      - backend\n\
    ports: \n\
      - 8020:8050\n\
    volumes:\n\
      - *data-volume\n\
      - *docker-socket\n\
\n\
networks:\n\
  backend:\n\
    name: backend\n\
  frontend:\n\
    name: frontend\n"

echo -e "${DC_FILE_CONTENT}" > docker-compose.yml

DC_DOWN_CMD="docker compose \
    -f docker-compose.yml \
    down \
        --rmi all \
        -v \
        --remove-orphans"

DC_UP_CMD="docker compose \
    -f docker-compose.yml \
    up \
        -d \
        --always-recreate-deps \
        --pull always"

eval "$DC_DOWN_CMD"
eval "$DC_UP_CMD"
