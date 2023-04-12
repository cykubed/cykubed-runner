ARG TAG=1.0
FROM europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-base:$TAG

#USER root
RUN curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | gpg --dearmor | tee /usr/share/keyrings/nodesource.gpg > /dev/null
RUN curl -sLf -o /dev/null 'https://deb.nodesource.com/node_16.x/dists/bullseye/Release'
COPY dockerfiles/node16.x/nodesource.list /etc/apt/sources.list.d/nodesource.list

RUN apt-get update && apt-get install nodejs

# Yarn 1.x for now
RUN npm install --global yarn

#USER cykube

COPY src .

ENTRYPOINT ["python", "main.py"]
