FROM us-docker.pkg.dev/cykubed/public/base-node-16:2.0.3

# install Firefox browser
RUN wget --no-verbose -O /tmp/firefox.tar.bz2 https://download-installer.cdn.mozilla.net/pub/firefox/releases/117.0/linux-x86_64/en-US/firefox-117.0.tar.bz2 && \
  tar -C /opt -xjf /tmp/firefox.tar.bz2 && \
  rm /tmp/firefox.tar.bz2 && \
  ln -fs /opt/firefox/firefox /usr/bin/firefox
