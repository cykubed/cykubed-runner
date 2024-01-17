FROM ubuntu:jammy

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ARG NODE=16

# === INSTALL Python ===

RUN apt-get update && \
    # Install Python
    apt-get install -y python3 python3-distutils curl python3-venv git-core xvfb wget && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python get-pip.py && \
    rm get-pip.py && \
    # Feature-parity with node.js base images.
    apt-get install -y --no-install-recommends git openssh-client gpg && \
    # clean apt cache
    rm -rf /var/lib/apt/lists/* && \
    # Create the pwuser
    adduser pwuser

# Install Node
RUN curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | gpg --dearmor | tee /usr/share/keyrings/nodesource.gpg > /dev/null
RUN curl -sLf -o /dev/null "https://deb.nodesource.com/node_${NODE}.x/dists/bullseye/Release"
RUN echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE}.x bullseye main" | tee /etc/apt/sources.list.d/nodesource.list
RUN apt-get update && apt-get install nodejs -y
RUN npm install --global yarn

RUN pip install poetry==1.3.1

# === BAKE BROWSERS INTO IMAGE ===

RUN mkdir /browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/browers
RUN npx playwright install --with-deps && \
    rm -rf ~/.npm/ && \
    chmod -R 777 /browsers

# Cykubed prep
WORKDIR /usr/app
RUN mkdir /node /build
RUN useradd -m cykubed --uid 10000 && chown cykubed:cykubed /usr/app /node /build
