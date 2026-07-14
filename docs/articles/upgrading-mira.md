# 

## How to upgrade MIRA to the lastest version

MIRA version 1 was installed with a data directory of
`FLU_SC2_SEQUENCING`, versions 2.0.0+ are reccomended to be installed
with `MIRA_NGS` as the data directory. If you are upgrading from v1.1.X,
you may wish to retain your `FLU_SC2_SEQUENCING` folder as the MIRA data
location.

### Upgrading MIRA with four containers (version 1.1.4) to MIRA single container (version 2.0.0)

1.  Open a terminal (Ubuntu if you installed WSL2 with this
    instructions, Terminal if you are using a Mac). `cd` to the folder
    with your sequence run data:

    ``` bash
     cd ~/FLU_SC2_SEQUENCING
    ```

2.  Remove current running MIRA containers:

    ``` bash
     docker rm -f mira spyne irma dais
    ```

3.  Remove older MIRA image versions (or iSpy or IRMA-spy if that’s what
    you had installed)

    ``` bash
     sudo docker rmi -f $(docker images | grep -e irma -e dais -e mira -e spyne | tr -s " " | cut -f3 -d" ")
    ```

4.  Download the installation script from the internet:

    ``` bash
     curl https://raw.githubusercontent.com/CDCgov/MIRA/prod/docker-compose-cdcgov.yml | sed "s%/path/to/data%$(pwd)/%g" > docker-compose.yml
    ```

    *if you get a permissions error here, first run
    `sudo rm docker-compose.yml` then try again*

5.  After you ensure that your Docker Desktop application is open, run
    the install script with `sudo` and `docker compose`:

    ``` bash
     sudo docker compose up -d
    ```

### Upgrading MIRA single container (version 2.0.0+)

1.  Open a terminal (Ubuntu if you installed WSL2 with this
    instructions, Terminal if you are using a Mac). `cd` to the folder
    with your sequence run data:

    ``` bash
     cd ~/MIRA_NGS
    ```

2.  Remove current running MIRA container:

    ``` bash
     docker rm -f mira
    ```

3.  Remove older MIRA image version:

    ``` bash
     sudo docker rmi -f $(docker images | grep -e mira | tr -s " " | cut -f3 -d" ")
    ```

4.  Download the installation script from the internet:

    ``` bash
     curl https://raw.githubusercontent.com/CDCgov/MIRA/prod/docker-compose-cdcgov.yml | sed "s%/path/to/data%$(pwd)/%g" > docker-compose.yml
    ```

    *if you get a permissions error here, first run
    `sudo rm docker-compose.yml` then try again*

5.  After you ensure that your Docker Desktop application is open, run
    the install script with `sudo` and `docker compose`:

    ``` bash
     sudo docker compose up -d
    ```
