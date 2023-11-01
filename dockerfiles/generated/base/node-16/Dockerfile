FROM us-docker.pkg.dev/cykubed/public/base:2.0.3

RUN curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | gpg --dearmor | tee /usr/share/keyrings/nodesource.gpg > /dev/null
RUN curl -sLf -o /dev/null 'https://deb.nodesource.com/node_16.x/dists/bullseye/Release'
RUN echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_16.x bullseye main" | tee /etc/apt/sources.list.d/nodesource.list
RUN apt-get update && apt-get install nodejs -y
RUN npm install --global yarn
