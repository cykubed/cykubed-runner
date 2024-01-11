ARG tag=1.0
FROM $region-docker.pkg.dev/cykubed/public/base:$tag

RUN curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | gpg --dearmor | tee /usr/share/keyrings/nodesource.gpg > /dev/null
RUN curl -sLf -o /dev/null 'https://deb.nodesource.com/node_${node_major}.x/dists/bullseye/Release'
RUN echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${node_major}.x bullseye main" | tee /etc/apt/sources.list.d/nodesource.list
RUN apt-get update && apt-get install nodejs -y
RUN npm install --global yarn
