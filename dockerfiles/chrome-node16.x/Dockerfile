ARG TAG=1.0
FROM nickbrookck/cykube-runner:chrome90-$TAG

USER root

RUN curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | gpg --dearmor | tee /usr/share/keyrings/nodesource.gpg > /dev/null
RUN curl -sLf -o /dev/null 'https://deb.nodesource.com/node_16.x/dists/bullseye/Release'
COPY dockerfiles/node16.x/nodesource.list /etc/apt/sources.list.d/nodesource.list

RUN apt-get update && apt-get install nodejs
USER cykube

COPY src .

ENTRYPOINT ["poetry", "run", "python", "main.py"]
