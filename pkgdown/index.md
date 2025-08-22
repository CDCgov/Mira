

# <img src="man/figures/logo.png" align="left" width="190" /> MIRA: Portable, Interactive Application for High-Quality Influenza, SARS-CoV-2 and RSV Genome Assembly, Annotation, and Curation

![pkgdown](https://github.com/cdcgov/mira/workflows/pkgdown/badge.svg)
![Docker pulls](https://img.shields.io/docker/pulls/cdcgov/mira)
![Docker image size](https://img.shields.io/docker/image-size/cdcgov/mira) 
![GitHub last commit](https://img.shields.io/github/last-commit/cdcgov/mira)

<br>

**General disclaimer** This repository was created for use by CDC
programs to collaborate on public health related projects in support of
the [CDC mission](https://www.cdc.gov/about/divisions-offices/index.html).
GitHub is not hosted by the CDC, but is a third party website used by
CDC and its partners to share information and collaborate on software.
CDC use of GitHub does not imply an endorsement of any one particular
service, product, or enterprise.

<hr>
<br>

# Get Started with MIRA Today! 
_[Quick start on Ubuntu OS](./articles/quick-start-ubuntu.html)_

<img src="man/figures/mira-tutorial.gif" alt="Running MIRA" width="800" height="700">


# Overview

**MIRA** is a bioinformatics pipeline that assembles Influenza genomes, SARS-CoV-2 genomes, 
the SARS-CoV-2 spike-gene and RSV genomes when given the raw fastq files and a samplesheet. 
MIRA can assemble reads from both Illumina and OxFord Nanopore sequencing machines. _Coming soon, 
it will automate sequence submission to NCBI's [**Genbank**](https://www.ncbi.nlm.nih.gov/genbank/), [**BioSample**](https://www.ncbi.nlm.nih.gov/biosample/), and [**SRA**](https://www.ncbi.nlm.nih.gov/sra/), as well 
as [**GISAID**](https://gisaid.org/) using [SeqSender](https://cdcgov.github.io/seqsender/)._

![](man/figures/MIRA_flowchart_pptx.png)

<hr>

## Which MIRA is right for you?
All versions of MIRA process raw sequencing reads into 
consensus genomes using the same pipeline and quality control. All versions create an interactive
quality report and multi-fastas ready for public database submission.

### Running MIRA with Docker Desktop (MIRA-GUI)
MIRA-GUI is the most popular choice for laboratory scientists. It runs on a local computer and is 
ideal for users who are not comfortable using the command line. 

Computational Requirements:

- A minimum of 16GB of memory is required. >=32GB is recommended.
- A minimum of 8 CPU cores. 16 are recommended.

Skill Needed:

- Ability to install software on a computer.

Key features:

- **No command line needed!**
- Easy to use Graphical User Interface (GUI).

To run MIRA with Docker Desktop you can get started [here](./articles/mira-dd-getting-started.html).

### Running MIRA on the command line (MIRA-CLI) with Docker
MIRA-CLI runs on a local computer from the command line. It is ideal for users who are familiar with
running scripts from a terminal and are interested in automating MIRA analyses into local pipelines.  

Computational Requirements: 

- A minimum of 16GB of memory is required. >=32GB is recommended.
- A minimum of 8 CPU cores. 16 are recommended.
- **Administrative privileges are required on a Windows operating system _to run linux_.**
- A linux/unix (includes MacOS*) operating system is required.
    - This software **does work** on Apple's M-chip based OS, _however we have observed intermittent instability issues._
    - If you are using a Mac, [go to Mac Getting Started.](./articles/mira-cli-mac-getting-started.html)

Skill Needed:

- Ability to navigate your command line and run commands. 

Key features:

- Interactive and sharable HTML reports.

To run MIRA-CLI you can get started with our [Quick Start for Ubuntu instructions](./articles/quick-start-ubuntu.html), [PC instructions](./articles/getting-started.html) or [Mac instructions](./articles/mira-cli-mac-getting-started.html).

### Running MIRA-NF with Nextflow
MIRA-NF runs on a high performing computing (HPC) cluster or in a cloud computing platform. It is ideal 
for users who have access to an HPC and want to process a large volume of samples.

Computational Requirements:

- Access to an HPC or cloud computing platform.

Skill Needed:

- Familiarity with analyzing data in HPC and cloud computing platforms. 
- Strong understanding of command line interface.

Key features:

- Able to run large data sets _without the need for subsampling._
- Interactive and sharable HTML reports.

### To run MIRA-NF you can get started by cloning the [MIRA-NF Repo](https://github.com/CDCgov/MIRA-NF)!

<hr>

## Test your MIRA Setup
    
- [Click here to download tiny test data from ONT Influenza genome and SARS-CoV-2-spike - 40Mb](https://centersfordiseasecontrol.sharefile.com/d-s839d7319e9b04e2baba07b4d328f02c2)
- [Click here for the above data set + full genomes of Influenza and SARS-CoV-2 from Illumina MiSeqs - 1Gb](https://centersfordiseasecontrol.sharefile.com/d-s3c52c0b25c2243078f506d60bd787c62)
- unzip the file and find two folders:
    1. `tiny_test_run_flu`
    2. `tiny_test_run_sc2`
- move these folders into `MIRA_NGS`
  - if you cannot find the MIRA_NGS folder in your Linux section of file explorer, look in <br> Linux --> home --> your username


