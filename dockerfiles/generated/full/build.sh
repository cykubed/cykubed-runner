#!/bin/bash
set -e
docker build -t us-docker.pkg.dev/cykubed/public/base-runner:3.20.70 -f dockerfiles/base/runner/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16:3.20.70 -f dockerfiles/generated/full/node-16/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-firefox:3.20.70 -f dockerfiles/generated/full/node-16-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-chrome:3.20.70 -f dockerfiles/generated/full/node-16-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-edge:3.20.70 -f dockerfiles/generated/full/node-16-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18:3.20.70 -f dockerfiles/generated/full/node-18/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18-firefox:3.20.70 -f dockerfiles/generated/full/node-18-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18-chrome:3.20.70 -f dockerfiles/generated/full/node-18-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18-edge:3.20.70 -f dockerfiles/generated/full/node-18-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20:3.20.70 -f dockerfiles/generated/full/node-20/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20-firefox:3.20.70 -f dockerfiles/generated/full/node-20-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20-chrome:3.20.70 -f dockerfiles/generated/full/node-20-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20-edge:3.20.70 -f dockerfiles/generated/full/node-20-edge/Dockerfile .
