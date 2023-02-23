FROM python:3.10.9-slim-bullseye

RUN apt-get update && \
  apt-get install --no-install-recommends -y \
  curl \
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
  vim-tiny \
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

RUN useradd -m cykube && chown cykube /usr/app
USER cykube

RUN mkdir /tmp/cykube
ENV PATH="/home/cykube/.local/bin:/tmp/cykube/build/node_modules/.bin:$PATH"
RUN CYPRESS_CACHE_FOLDER=/tmp/cykube/build/cypresscache

RUN pip install poetry==1.3.1
COPY pyproject.toml poetry.lock ./
RUN poetry config installer.max-workers 10
RUN poetry install --no-root --without=dev

