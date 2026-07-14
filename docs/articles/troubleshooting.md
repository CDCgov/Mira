# 

## Troubleshooting

------------------------------------------------------------------------

### MIRA installation failed

MIRA installation with docker compose expects an Ubuntu 18+ operating
system or WSL2 distribution. If you have this, perform the following:

1.  Restart your computer

2.  Add google’s domain name server (DNS) to /etc/resolv.confirm

    ``` bash
    sudo echo 8.8.8.8 >> /etc/resolv.conf
    ```

3.  Open Docker Desktop and select all containers and Delete them. ![alt
    text](images/mira_docker_delete_containers.png)![alt
    text](images/mira_docker_delete_images.png)

4.  Go to [Installing
    MIRA](https://cdcgov.github.io/MIRA/articles/mira-installation.md)

[Return to contents](#Contents)

------------------------------------------------------------------------

### My containers are running in Ubuntu, but I don’t see them in Docker Desktop

Following successful installation, you should see your containers
running in Ubuntu and in Docker Desktop. However, if you have multiple
Ubuntu distributions installed, you may need to enable the right one in
Docker Desktop.

Click the “Settings” icon in the top right corner of Docker Desktop,
then Resources, then WSL Integration. Here, you can enable the right
distribution if you see multiple Ubuntu versions listed:

![](images/WSL_docker.png)

  
Then click Apply and Restart

### WSL install error

From the Windows search bar, open `Turn Windows Features on or off` and
make sure the following 4 features are enabled:

- Hyper-V
- Virtual Machine Platform
- Windows Hypervisor Platform
- Windows Subsystem for Linux

### apt-get update error

If your `apt-get update` fails with a message related to certificates
not valid for another 3 hours (for example), this means your computer
time zone does not match Ubuntu time zone. Change your Windows time to
auto-update and match the current timezone, then try again.

### Map network drive

\*\**Many computers have trouble with this step; the folders are not
selectable during this step. First, make sure that an Ubuntu terminal is
opened and then open the `File Explorer`. If “Ubuntu” is still not
showing up in `File Explorer`, you can try to find the solution here:
<https://github.com/microsoft/WSL/issues/3996>.*

1.  Open [File
    Explorer](https://cdcgov.github.io/MIRA/articles/images/file_explorer.png)

    - *If you have a Windows 10 or 11 OS, WSL is likely automatically
      mapped and visible in the left hand sidebar as “Ubuntu”*

2.  Right click [This PC and click Map network
    drive](https://cdcgov.github.io/MIRA/articles/images/map_drive_1.png)

3.  Enter `\\wsl$` into Folder: [and click
    Browse](https://cdcgov.github.io/MIRA/articles/images/map_drive_2.png)

4.  Click on `wsl$` to unfold directories, select `Ubuntu-18.04` [and
    click
    OK](https://cdcgov.github.io/MIRA/articles/images/map_drive_3.png)
    and then `Finish`. You should now see your WSL “drive” available in
    `File Explorer`:

    ![](images/map_drive_4.png)

### Docker CLI errors

- If you get an error related to starting Docker, run the following
  command, then try to run hello-world again

``` bash
sudo service docker start
```

- If you get an error related to “Permission Denied” of docker.sock, run
  the following command, then try to run hello-world again

``` bash
sudo chmod -755 /run/docker.sock
```

- If your hello-world container still is not showing, open the
  Ubuntu-22.04 command prompt and run:

``` bash
docker run -d -p 80:80 docker/getting-started
```

### Virtualization error

- If you see a message relating to Virtualization needing to be enabled,
  follow instructions below to access your machine’s BIOS setup:
  - [Windows 11 virtualization
    instructions](https://support.microsoft.com/en-us/windows/enable-virtualization-on-windows-11-pcs-c5578302-6e43-4b4b-a449-8ced115f58e1)
  - [Windows 10 virtualization
    instructions](https://www.geeksforgeeks.org/how-to-enable-virtualization-vt-x-in-windows-10-bios/)

[Return to contents](#Contents)
