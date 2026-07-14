# 

## MIRA installation

MIRA runs inside Docker containers. Containers have all of the code and
dependencies necessary to run MIRA and only have access to user defined
folders or sockets on your computer.

------------------------------------------------------------------------

1.  Open a terminal (Ubuntu if you installed WSL2 with [these
    instructions](https://cdcgov.github.io/MIRA/articles/getting-started.md),
    Terminal if you are using a Mac or Linux OS). Create a folder to
    store your sequence run data and change to that directory. This
    folder was previously called `FLU_SC2_SEQUENCING` in documentation
    predating September 2024:

    ``` bash
     mkdir ~/MIRA_NGS
    ```

    ``` bash
     cd ~/MIRA_NGS
    ```

2.  Download the installation script from the internet:

    ``` bash
     curl https://raw.githubusercontent.com/CDCgov/MIRA/prod/docker-compose-cdcgov.yml | sed "s%/path/to/data%$(pwd)/%g" > docker-compose.yml
    ```

3.  Run the install script with `docker-compose`:

    ``` bash
     docker compose up -d
    ```

If this command returns an error relating to permissions, try again with
`sudo` before the docker compose call

4.  The download should begin and a lot of information will begin to
    appear in your terminal such as:

         ⠿ mira Warning                                                                                                                                                                                                                                          2.2s

        ⠿ 3b65ec22a9e9 Pull complete                                                                                                                                                                                                                         16.9s
        ⠿ 4f4fb700ef54 Download complete                                                                                                                                                                                                                     35.4s
        ⠿ 1c1f5954eb75 Pull complete                                                                                                                                                                                                                         18.7s
        ⠿ 09b185cd9896 Pull complete                                                                                                                                                                                                                         18.9s
        ⠿ 45c1caf84255 Pull complete                                                                                                                                                                                                                         19.0s
        ⠼ e8372b04cf6b Downloading [===================================>               ]  68.14MB/97.25MB                                                                                                                                                    35.4s
        ⠼ fcce5f3f42f5 Download complete                                                                                                                                                                                                                     35.4s
        ⠼ d897b2636a18 Download complete                                                                                                                                                                                                                     35.4s
        ⠼ 2d6fb277dca0 Download complete                                                                                                                                                                                                                     35.4s
        ⠼ c5227e837167 Download complete                                                                                                                                                                                                                     35.4s
        ⠼ 4b4467648e29 Download complete                                                                                                                                                                                                                     35.4s
        ⠸ 675920708c8b Extracting [========================>                          ]  14.16MB/28.57MB                                                                                                                                                     35.4s
        ⠸ e69b9363318d Downloading [==========================>                        ]  14.48MB/27.07MB                                                                                                                                                    35.4s
        ⠸ 59f3820cb75a Download complete                                                                                                                                                                                                                     35.4s
        ⠸ 96523e405125 Downloading [=====>                                             ]  1.286MB/11.16MB                                                                                                                                                    35.4s
        ⠸ b6da8f73ba02 Waiting                                                                                                                                                                                                                               35.4s
        ⠸ f85e87677f9a Waiting                                                                                                                                                                                                                               35.4s
        ⠸ 5ceb0311151f Waiting                                                                                                                                                                                                                               35.4s
        ⠸ ae01c60d8873 Waiting                                                                                                                                                                                                                               35.4s

    MIRA is about 800 MB in total size and may take a long time to
    download [depending on your internet
    speed](https://www.omnicalculator.com/other/download-time), ie:

    | Internet Speed | Download Time     |
    |----------------|-------------------|
    | 500 Kbps       | 3 hour 33 minutes |
    | 10 Mbps        | 11 minutes        |
    | 25 Mbps        | 4 minutes         |
    | 100 Mpbs       | 1 minute          |

5.  A successful installation will end with your terminal showing:

        [+] Running 1/1
         ⠿ Container mira    Started     

- If your installation is not successful, please refer to
  [Troubleshooting](https://cdcgov.github.io/MIRA/articles/troubleshooting.md)
  or email us at <idseqsupport@cdc.gov>

### Test your MIRA Setup

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
  - if you cannot find the MIRA_NGS folder in your Linux section of file
    explorer, look in Linux–\>home–\>your username

#### Upon successful installation, you can proceed to running MIRA with [Oxford Nanopore data](https://cdcgov.github.io/MIRA/articles/running-mira-cli.md) or [Illumina data](https://cdcgov.github.io/MIRA/articles/running-mira-cli-illumina.md)
