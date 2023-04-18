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

RUN mkdir /build

RUN useradd -m cykube --uid 10000 && chown cykube /usr/app
USER cykube

ENV PATH="/usr/app/.venv/bin:/home/cykube/.local/bin:/tmp/build/node_modules/.bin:$PATH"
ENV POETRY_VIRTUALENVS_IN_PROJECT=1

RUN pip install poetry==1.3.1
COPY pyproject.toml poetry.lock ./
RUN poetry config installer.max-workers 10
#RUN poetry install --no-root --without=dev
RUN poetry install --no-root --with=dev

