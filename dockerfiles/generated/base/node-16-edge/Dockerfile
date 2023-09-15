FROM us-docker.pkg.dev/cykubed/public/base-node-16:2.0.1

## Setup Edge
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
RUN install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/
RUN sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge-dev.list'
RUN rm microsoft.gpg
## Install Edge
RUN apt-get update
RUN apt-get install -y microsoft-edge-dev

# Add a link to the browser that allows Cypress to find it
RUN ln -s /usr/bin/microsoft-edge /usr/bin/edge
