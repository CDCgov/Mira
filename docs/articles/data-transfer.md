# 

## Data Transfer from the Mk1C Sequencing Device for Downstream Analysis

*Once your MinION Mk1C sequencing run completes, these instructions
detail how to transfer your reads from the machine to your computer
using a flash drive, staging them for assembly and analysis with MIRA*

------------------------------------------------------------------------

### 1. Plug your USB storage device into the side of the MK1C

### 2. On the MK1C screen, select File Manager and navigate into your runid

### 3. Navigate down to the “fastq_pass” folder and select the three dots to the right of it

### 4. Select copy, then you should be prompted to select “external drive”

### 5. Prepare your runfolder on your computer

- Prepare the ExperimentID folder
  - In files, navigate to Linux –\> home –\> \[user\] –\> MIRA_NGS
    (Windows WSL) or FLU_SC2_SEQUENCING, depending on how you set up you
    MIRA installation
  - Inside of this folder, create a new folder with your RUN ID
    - Run IDs generally should contain the date sequenced and the
      pathogen

### 6. Move your fastq_pass folder from the USB drive into this RUNID folder

- You do NOT NEED to include the “unclassified” folder, since it is
  large and has unusable data

#### You now have staged yout Mk1C fastqs for analysis! You can proceed to [Running MIRA](https://cdcgov.github.io/MIRA/articles/running-mira-dd-ont.md)
