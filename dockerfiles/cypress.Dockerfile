FROM python:3.10-slim-bullseye
ARG firefox_version=133.0
ARG node=22

RUN apt-get update && \
  apt-get install --no-install-recommends -y \
  curl \
  bzip2 \
  ca-certificates \
  libgtk2.0-0 \
  libgtk-3-0 \
  libnotify-dev \
  libgconf-2-4 \
  libgbm-dev \
  libnss3 \
  libxss1 \
  libasound2 \
  libxtst6 \
  procps \
  xauth \
  xvfb \
  # install text editors
  vim \
  # install emoji font
  fonts-noto-color-emoji \
  # install Chinese fonts
  # this list was copied from https://github.com/jim3ma/docker-leanote
  fonts-arphic-bkai00mp \
  fonts-arphic-bsmi00lp \
  fonts-arphic-gbsn00lp \
  fonts-arphic-gkai00mp \
  fonts-arphic-ukai \
  fonts-arphic-uming \
  ttf-wqy-zenhei \
  ttf-wqy-microhei \
  xfonts-wqy \
  gnupg \
  lz4 \
  bash \
  git-core \
  wget \
  # clean up
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean

WORKDIR /usr/app
RUN mkdir /node /build

ENV PATH="/home/cykubed/.local/bin:$PATH"
ENV TZ=UTC

# install Chrome browser
RUN wget --no-verbose -O /usr/src/google-chrome-stable_current_amd64.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" && \
  dpkg -i /usr/src/google-chrome-stable_current_amd64.deb ; \
  apt-get install -f -y && \
  rm -f /usr/src/google-chrome-stable_current_amd64.deb

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

# install Firefox browser
RUN wget --no-verbose -O /tmp/firefox.tar.bz2 https://download-installer.cdn.mozilla.net/pub/firefox/releases/$firefox_version/linux-x86_64/en-US/firefox-$firefox_version.tar.bz2 && \
  tar -C /opt -xjf /tmp/firefox.tar.bz2 && \
  rm /tmp/firefox.tar.bz2 && \
  ln -fs /opt/firefox/firefox /usr/bin/firefox

SHELL ["/bin/bash", "--login", "-c"]

# install the runner
RUN pip install poetry

RUN useradd -m cykubed --uid 10000 && chown cykubed:cykubed /usr/app /node /build

USER cykubed

# install node
ENV NVM_DIR="/usr/app/nvm"
RUN mkdir -p $NVM_DIR
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
RUN /bin/bash -c "source $NVM_DIR/nvm.sh && nvm install $node --default --save"
RUN python -m venv .venv

ENV VIRTUAL_ENV=/usr/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/usr/app:.

COPY src/cykubedrunner cykubedrunner
COPY ["pyproject.toml", "poetry.lock", "./"]

RUN poetry install --no-root --only main --no-interaction

ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
