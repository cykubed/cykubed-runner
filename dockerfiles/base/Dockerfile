FROM python:3.10-slim-bullseye

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

RUN useradd -m cykubed --uid 10000 && chown cykubed:cykubed /usr/app /node /build
# Note: derived images should switch to cukubed user to avoid running as root

ENV PATH="/home/cykubed/.local/bin:$PATH"
ENV TZ=UTC

RUN pip install poetry==1.3.1
