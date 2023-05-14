ARG TAG=1.0
FROM europe-docker.pkg.dev/cykubeapp/cykubed/runner-base:$TAG

USER root
RUN curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | gpg --dearmor | tee /usr/share/keyrings/nodesource.gpg > /dev/null
RUN curl -sLf -o /dev/null 'https://deb.nodesource.com/node_16.x/dists/bullseye/Release'
COPY dockerfiles/node16.x/nodesource.list /etc/apt/sources.list.d/nodesource.list

RUN apt-get update && apt-get install nodejs

# install Chrome browser
RUN wget --no-verbose -O /usr/src/google-chrome-stable_current_amd64.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" && \
  dpkg -i /usr/src/google-chrome-stable_current_amd64.deb ; \
  apt-get install -f -y && \
  rm -f /usr/src/google-chrome-stable_current_amd64.deb

# Yarn 1.x for now
RUN npm install --global yarn

USER 10000
#USER root

COPY src .

ENTRYPOINT ["python", "main.py"]
