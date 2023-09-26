#!/bin/bash
set -e
docker build -t us-docker.pkg.dev/cykubed/public/base-runner:3.19.5 -f dockerfiles/base/runner/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16:3.19.5 -f dockerfiles/generated/full/node-16/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-firefox:3.19.5 -f dockerfiles/generated/full/node-16-firefox/Dockerfile .
