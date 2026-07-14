# 

## Frequently asked questions

### How do I get help?

Great question!!

MIRA is under active development. If you need help, would like to
contribute, or simply want to talk about the project with like-minded
individuals, we have a number of open channels for communication.

- Send us an email at [idseqsupport@cdc.gov](mailto:idseqsupport.gov)

- To report bugs or file feature requests, use the [issue tracker on
  Github](https://github.com/CDCgov/MIRA/issues).

- To contribute code submit a [pull request on
  Github](https://github.com/CDCgov/MIRA/pulls).

### How to remove containers. This is a good idea if you are having trouble with your version and need a fresh start. This will not have any effect on your sequencing data.

#### iSpy uninstall

``` bash
docker stop ispy
docker rm ispy
docker rmi ispy
```

#### IRMA-SPY uninstall

``` bash
docker stop irma-spy
docker rm irma-spy
docker rmi irma-spy
```

#### MIRA uninstall

1.  Open an Ubuntu terminal

2.  ``` bash
     # Show running containers
     docker ps

     # Stop running container you want to update. In this example we are updating mira and spyne.
     docker stop mira spyne irma dais

     # Delete containers
     docker rm mira spyne irma dais

     # Delete images
     docker rmi mira spyne irma dais
    ```

3.  Install the new MIRA and spyne containers: [See Docker Desktop MIRA
    installation](https://cdcgov.github.io/MIRA/articles/mira-dd-getting-started.md)

### How do I customize the number of cores MIRA uses?

This is best achieved by setting `resources` in the `docker-compose.yml`
for a container’s `deploy` settings:

For example:

``` bash
spyne: 
    container_name: spyne
    image: spyne
    build: 
      context: *spyne-git-version 
    depends_on:
      - dais
      - irma
    restart: always
    networks:
      - backend
    volumes:
      - *data-volume
      - *docker-socket
    command: tail -f /dev/null
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 50M
        reservations:
          cpus: '0.25'
          memory: 20M
```

Read more
[here](https://docs.docker.com/compose/compose-file/compose-file-v3/#resources)
in the official Docker Docs

  

### Docker compose operations

| Command | Description |
|----|----|
| [docker compose build](https://docs.docker.com/engine/reference/commandline/compose_build/) | Build or rebuild services |
| [docker compose config](https://docs.docker.com/engine/reference/commandline/compose_config/) | Parse, resolve and render compose file in canonical format |
| [docker compose cp](https://docs.docker.com/engine/reference/commandline/compose_cp/) | Copy files/folders between a service container and the local filesystem |
| [docker compose create](https://docs.docker.com/engine/reference/commandline/compose_create/) | Creates containers for a service. |
| [docker compose down](https://docs.docker.com/engine/reference/commandline/compose_down/) | Stop and remove containers, networks |
| [docker compose events](https://docs.docker.com/engine/reference/commandline/compose_events/) | Receive real time events from containers. |
| [docker compose exec](https://docs.docker.com/engine/reference/commandline/compose_exec/) | Execute a command in a running container. |
| [docker compose images](https://docs.docker.com/engine/reference/commandline/compose_images/) | List images used by the created containers |
| [docker compose kill](https://docs.docker.com/engine/reference/commandline/compose_kill/) | Force stop service containers. |
| [docker compose logs](https://docs.docker.com/engine/reference/commandline/compose_logs/) | View output from containers |
| [docker compose ls](https://docs.docker.com/engine/reference/commandline/compose_ls/) | List running compose projects |
| [docker compose pause](https://docs.docker.com/engine/reference/commandline/compose_pause/) | Pause services |
| [docker compose port](https://docs.docker.com/engine/reference/commandline/compose_port/) | Print the public port for a port binding. |
| [docker compose ps](https://docs.docker.com/engine/reference/commandline/compose_ps/) | List containers |
| [docker compose pull](https://docs.docker.com/engine/reference/commandline/compose_pull/) | Pull service images |
| [docker compose push](https://docs.docker.com/engine/reference/commandline/compose_push/) | Push service images |
| [docker compose restart](https://docs.docker.com/engine/reference/commandline/compose_restart/) | Restart service containers |
| [docker compose rm](https://docs.docker.com/engine/reference/commandline/compose_rm/) | Removes stopped service containers |
| [docker compose run](https://docs.docker.com/engine/reference/commandline/compose_run/) | Run a one-off command on a service. |
| [docker compose start](https://docs.docker.com/engine/reference/commandline/compose_start/) | Start services |
| [docker compose stop](https://docs.docker.com/engine/reference/commandline/compose_stop/) | Stop services |
| [docker compose top](https://docs.docker.com/engine/reference/commandline/compose_top/) | Display the running processes |
| [docker compose unpause](https://docs.docker.com/engine/reference/commandline/compose_unpause/) | Unpause services |
| [docker compose up](https://docs.docker.com/engine/reference/commandline/compose_up/) | Create and start containers |
| [docker compose version](https://docs.docker.com/engine/reference/commandline/compose_version/) | Show the Docker Compose version information |
