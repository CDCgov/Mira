# 

QUICK START STUFF: \## Quick Start on Ubuntu OS: *Need to set up an
Ubuntu OS? Follow instructions in [Getting
Started.](https://cdcgov.github.io/MIRA/articles/getting-started.md)*

### Install Docker CLI and Docker Compose:

``` bash
sudo apt-get update
```

``` bash
sudo apt-get install ca-certificates curl gnupg lsb-release
```

- During installation, you will be prompted to enter ‘y’ or ‘n’ to
  proceed. Each time, input ‘y’ and click `Enter`

``` bash
sudo mkdir -p /etc/apt/keyrings
```

``` bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
```

``` bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

``` bash
sudo apt-get update
```

``` bash
sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

``` bash
sudo apt-get update
```

``` bash
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

5.  Verify successful installation

``` bash
sudo docker run hello-world
```

- This command downloads a test image and runs it in a container. When
  the container runs, it prints a confirmation message and exits.

### MIRA Container Installation with Docker Compose

- Create a folder called `MIRA_NGS` to save your sequencing reads to.
  From the command line, run:

``` bash
mkdir ~/MIRA_NGS

cd ~/MIRA_NGS
```

- Download the install yml:

``` bash
 curl https://raw.githubusercontent.com/CDCgov/MIRA/prod/docker-compose-cdcgov.yml | sed "s%/path/to/data%$(pwd)/%g" > docker-compose.yml
```

- Run the install script:

``` bash
sudo docker compose up -d
```

## Test your MIRA Setup

- [Click here to download tiny test data from ONT Influenza genome and
  SARS-CoV-2-spike -
  40Mb](https://centersfordiseasecontrol.sharefile.com/d-s839d7319e9b04e2baba07b4d328f02c2)
- [Click here for the above data set + full genomes of Influenza and
  SARS-CoV-2 from Illumina MiSeqs -
  1Gb](https://centersfordiseasecontrol.sharefile.com/d-s3c52c0b25c2243078f506d60bd787c62)
- unzip the file and find two folders:
  1.  `tiny_test_run_flu`
  2.  `tiny_test_run_sc2`
- move these folders into `MIRA_NGS`
  - if you cannot find the MIRA_NGS folder in your Linux section of file
    explorer, look in Linux–\>home–\>your username
- Open your browser and type <http://localhost:8020> in the address bar.
- Click `Refresh Run Listing` in MIRA, you should now see these folders
  listed.
- Click `Download Samplesheet`.
  - This will give you an excel sheet with available barcodes populated.
    Add in our samplenames for ONT data (Illumina data will self
    identify samplenames based on fastqs)
- Save the samplesheet and then upload it by clicking on
  `Drag and Drop your Samplesheet or Click and Select the File`
- In the dropdown box ‘What kind of data is this?’, select the correct
  data type.
  - If SC2 full genome, also select your primers.
- Click ‘START GENOME ASSEMBLY’
- Toggle ‘Watch IRMA progress’ to see IRMA’s stdout stream.
- When “IRMA is finished!” is displayed, Click “DISPLAY IRMA RESULTS”
