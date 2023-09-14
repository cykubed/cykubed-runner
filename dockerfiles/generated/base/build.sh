#!/bin/bash
set -e

docker build -t us-docker.pkg.dev/cykubed/public/base:2.0.1 -f dockerfiles/generated/base/base/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-14:2.0.1 -f dockerfiles/generated/base/node-14/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-14-chrome:2.0.1 -f dockerfiles/generated/base/node-14-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-14-edge:2.0.1 -f dockerfiles/generated/base/node-14-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-14-chrome-edge-firefox:2.0.1 -f dockerfiles/generated/base/node-14-chrome-edge-firefox/Dockerfile .

echo "{\"text\":\"Cykubed runner *base* images created with tag 2.0.1\"}" > slack_payload.json
/usr/bin/curl -X POST -H 'Content-type: application/json' --data "@slack_payload.json" $SLACK_HOOK_URL
