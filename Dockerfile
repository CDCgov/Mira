# Create an argument to pull a particular version of dias image
ARG spyne_image
ARG spyne_image=${spyne_image:-cdcgov/spyne:latest}

############# spyne image as base ##################
FROM ${spyne_image} as spyne
RUN echo "Getting spyne image"

# local apt mirror support
# start every stage with updated apt sources
ARG APT_MIRROR_NAME=
RUN if [ -n "$APT_MIRROR_NAME" ]; then sed -i.bak -E '/security/! s^https?://.+?/(debian|ubuntu)^http://'"$APT_MIRROR_NAME"'/\1^' /etc/apt/sources.list && grep '^deb' /etc/apt/sources.list; fi

# Install and update system libraries of general use
RUN apt-get update --allow-releaseinfo-change --fix-missing \
  && apt-get install --no-install-recommends -y \
  vim \
  dos2unix

# Create a working directory variable
ENV WORKDIR=/data

# Set up volume directory 
VOLUME ${WORKDIR}

# Set up working directory 
WORKDIR ${WORKDIR}

# Create a program variable
ENV MIRA_PROGRAM_DIR=/MIRA

# Set up volume directory 
VOLUME ${MIRA_PROGRAM_DIR}

# Copy all scripts to docker images
COPY . ${MIRA_PROGRAM_DIR}

############# Install python packages ##################

# Copy all files to docker images
COPY requirements.txt ${MIRA_PROGRAM_DIR}/requirements.txt

# Update pip and setuptools and then install python packages
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r ${MIRA_PROGRAM_DIR}/requirements.txt  

############# Fix vulnerablities pkgs ##################

# Copy all files to docker images
COPY fixed_vulnerability_pkgs.txt ${MIRA_PROGRAM_DIR}/fixed_vulnerability_pkgs.txt

# Copy all files to docker images
COPY fixed_vulnerability_pkgs.sh ${MIRA_PROGRAM_DIR}/fixed_vulnerability_pkgs.sh

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${MIRA_PROGRAM_DIR}/fixed_vulnerability_pkgs.sh

# Allow permission to excute the bash script
RUN chmod a+x ${MIRA_PROGRAM_DIR}/fixed_vulnerability_pkgs.sh

# Execute bash script to wget the file and tar the package
RUN bash ${MIRA_PROGRAM_DIR}/fixed_vulnerability_pkgs.sh    

############# Remove vulnerability pkgs ##################

# Copy all files to docker images
COPY remove_vulnerability_pkgs.txt ${MIRA_PROGRAM_DIR}/remove_vulnerability_pkgs.txt

# Copy all files to docker images
COPY remove_vulnerability_pkgs.sh ${MIRA_PROGRAM_DIR}/remove_vulnerability_pkgs.sh

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${MIRA_PROGRAM_DIR}/remove_vulnerability_pkgs.sh

# Allow permission to excute the bash script
RUN chmod a+x ${MIRA_PROGRAM_DIR}/remove_vulnerability_pkgs.sh

# Execute bash script to wget the file and tar the package
RUN bash ${MIRA_PROGRAM_DIR}/remove_vulnerability_pkgs.sh

############# Launch MIRA dashboard ##################

# Copy all files to docker images
COPY dashboard-kickoff ${MIRA_PROGRAM_DIR}/dashboard-kickoff

# Convert bash script from Windows style line endings to Unix-like control characters
RUN dos2unix ${MIRA_PROGRAM_DIR}/dashboard-kickoff

# Allow permission to excute the bash scripts
RUN chmod a+x ${MIRA_PROGRAM_DIR}/dashboard-kickoff

# Allow permission to read and write files to MIRA directory
RUN chmod -R a+rwx ${MIRA_PROGRAM_DIR}

# Make the app available at port 8050
EXPOSE 8050

# Clean up and remove unwanted files
RUN apt-get autoremove -y \
  && apt-get clean -y \
  && rm -rf /var/lib/{apt,dpkg,cache,log}/

# Export dais-ribosome script to path
ENV PATH "$PATH:/dais-ribosome"

# Export irma script to path
ENV PATH "$PATH:/flu-amd"

# Export spyne script to path
ENV PATH "$PATH:/spyne"

# Execute the pipeline 
ENTRYPOINT ["/bin/bash", "-c", "/MIRA/dashboard-kickoff"]
