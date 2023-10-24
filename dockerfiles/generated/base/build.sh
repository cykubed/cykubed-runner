#!/bin/bash
set -e

docker build -t us-docker.pkg.dev/cykubed/public/base:2.0.3 -f dockerfiles/generated/base/base/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-16:2.0.3 -f dockerfiles/generated/base/node-16/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-16-firefox:2.0.3 -f dockerfiles/generated/base/node-16-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-16-chrome:2.0.3 -f dockerfiles/generated/base/node-16-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-16-edge:2.0.3 -f dockerfiles/generated/base/node-16-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-16-chrome-edge-firefox:2.0.3 -f dockerfiles/generated/base/node-16-chrome-edge-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-18:2.0.3 -f dockerfiles/generated/base/node-18/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-18-firefox:2.0.3 -f dockerfiles/generated/base/node-18-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-18-chrome:2.0.3 -f dockerfiles/generated/base/node-18-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-18-edge:2.0.3 -f dockerfiles/generated/base/node-18-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-18-chrome-edge-firefox:2.0.3 -f dockerfiles/generated/base/node-18-chrome-edge-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-20:2.0.3 -f dockerfiles/generated/base/node-20/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-20-firefox:2.0.3 -f dockerfiles/generated/base/node-20-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-20-chrome:2.0.3 -f dockerfiles/generated/base/node-20-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-20-edge:2.0.3 -f dockerfiles/generated/base/node-20-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-20-chrome-edge-firefox:2.0.3 -f dockerfiles/generated/base/node-20-chrome-edge-firefox/Dockerfile .

echo "{\"text\":\"Cykubed runner *base* images created with tag 2.0.3\"}" > slack_payload.json
/usr/bin/curl -X POST -H 'Content-type: application/json' --data "@slack_payload.json" $SLACK_HOOK_URL
