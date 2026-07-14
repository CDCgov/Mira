# 

## [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)

Docker allows you to run software inside an isolated “container image”
on your computer with all of that application’s needed dependencies.
Make sure to install the version for your operating system.

- [Mac-Intel](https://desktop.docker.com/mac/main/amd64/Docker.dmg?utm_source=docker&utm_medium=webreferral&utm_campaign=dd-smartbutton&utm_location=module)
- [Mac-AppleChip](https://desktop.docker.com/mac/main/arm64/Docker.dmg?utm_source=docker&utm_medium=webreferral&utm_campaign=dd-smartbutton&utm_location=module)

## MIRA Installation

- Open Docker Desktop, and once it is running:

Open Settings -\> Features in development -\> Experimental Features:

- Ensure “Access Experimental Features” and “Enable backround SBOM
  Indexing” are both checked on

![](images/docker_features_in_development.png)

Next, in **Beta Features**, enable “Use Rosetta for x86/amd66 emulation
on Apple Silicon”. This will help MIRA run faster and remain more stable

Save these settings by clicking “Apply & restart”

### Open the terminal, and copy/paste these commands

\*NOTE: This `MIRA_NGS` folder was previously called
`FLU_SC2_SEQUENCING` in documentation predating September 2024

``` bash
mkdir ~/MIRA_NGS

cd ~/MIRA_NGS
```

``` bash
curl https://raw.githubusercontent.com/CDCgov/MIRA/prod/docker-compose-cdcgov.yml | sed "s%/path/to/data%$(pwd)/%g" > docker-compose.yml
```

``` bash
docker compose up -d
```

If the docker compose command fails with a permissions error, please try
again with `sudo` added before the command.

You are now running MIRA! You can proceed to Running MIRA with [Oxford
Nanopore data](https://cdcgov.github.io/MIRA/articles/running-mira.md)
or [Illumina
data](https://cdcgov.github.io/MIRA/articles/running-mira-illumina.md)

If these instructions show errors, please refer to our
[Troubleshooting](https://cdcgov.github.io/MIRA/articles/troubleshooting.md)
page or email us at <idseqsupport@cdc.gov>

## Optional: Install a sequence viewer to open output .fastas

- [Jalview](https://www.jalview.org/download/)

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
- move these 2b folders into `MIRA_NGS` so that the file structure looks
  like: `/MIRA_NGS/tiny_test_run_flu/fastq_pass/barcode##s/` and
  `/MIRA_NGS/tiny_test_run_sc2/fastq_pass/barcode##s/`

### Upon successful installation, you can proceed to running MIRA with [Oxford Nanopore data](https://cdcgov.github.io/MIRA/articles/running-mira-cli.md) or [Illumina data](https://cdcgov.github.io/MIRA/articles/running-mira-cli-illumina.md)
