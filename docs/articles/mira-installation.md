# 

## MIRA installation

MIRA runs inside Docker containers. Containers have all of the code and
dependencies necessary to run MIRA and only have access to user defined
folders or sockets on your computer.

------------------------------------------------------------------------

1.  Open a terminal (Ubuntu if you installed WSL2 with this
    instructions, Terminal if you are using a Mac). Create a folder to
    store your sequence run data and change to that directory:

    ``` bash
     mkdir ~/FLU_SC2_SEQUENCING
    ```

    ``` bash
     cd ~/FLU_SC2_SEQUENCING
    ```

2.  Download the installation script from the internet:

    ``` bash
     curl https://raw.githubusercontent.com/CDCgov/MIRA/prod/docker-compose-git.yml | sed "s%/path/to/data%$(pwd)/%g" > docker-compose.yml
    ```

3.  Run the install script with `sudo` and `docker-compose`:

    ``` bash
     sudo docker compose up -d
    ```

4.  The download should begin and a lot of information will begin to
    appear in your terminal such as:

         ⠿ mira Warning                                                                                                                                                                                                                                          2.2s
         ⠦ irma Pulling                                                                                                                                                                                                                                         37.7s
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
         ⠿ spyne Warning                                                                                                                                                                                                                                         2.2s
         ⠦ dais Pulling                                                                                                                                                                                                                                         37.7s
        ⠸ 675920708c8b Extracting [========================>                          ]  14.16MB/28.57MB                                                                                                                                                     35.4s
        ⠸ e69b9363318d Downloading [==========================>                        ]  14.48MB/27.07MB                                                                                                                                                    35.4s
        ⠸ 59f3820cb75a Download complete                                                                                                                                                                                                                     35.4s
        ⠸ 96523e405125 Downloading [=====>                                             ]  1.286MB/11.16MB                                                                                                                                                    35.4s
        ⠸ b6da8f73ba02 Waiting                                                                                                                                                                                                                               35.4s
        ⠸ f85e87677f9a Waiting                                                                                                                                                                                                                               35.4s
        ⠸ 5ceb0311151f Waiting                                                                                                                                                                                                                               35.4s
        ⠸ ae01c60d8873 Waiting                                                                                                                                                                                                                               35.4s

    MIRA is about 3 GB in total size and may take a long time to
    download [depending on your internet
    speed](https://www.omnicalculator.com/other/download-time), ie:

    | Internet Speed | Download Time     |
    |----------------|-------------------|
    | 500 Kbps       | 1 hour 28 minutes |
    | 10 Mbps        | 40 minutes        |
    | 25 Mbps        | 16 minutes        |
    | 100 Mpbs       | 4 minutes         |

5.  A successful installation will end with your terminal showing:

        [+] Running 6/6
         ⠿ Network frontend  Created     
         ⠿ Network backend   Created     
         ⠿ Container dais    Started     
         ⠿ Container irma    Started     
         ⠿ Container spyne   Started     
         ⠿ Container mira    Started     

- If your installation is not successful, please refer to
  [Troubleshooting: MIRA-INSTALL.sh
  failed](https://cdcgov.github.io/MIRA/articles/troubleshooting.md)

#### Upon successful installation, you can proceed to [Running MIRA](https://cdcgov.github.io/MIRA/articles/running-mira.md)
