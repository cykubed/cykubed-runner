#!/bin/bash
set -e

docker build -t us-docker.pkg.dev/cykubed/public/base:2.1.0 -f dockerfiles/generated/base/base/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-16:2.1.0 -f dockerfiles/generated/base/base/node-16/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-18:2.1.0 -f dockerfiles/generated/base/base/node-18/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/base-node-20:2.1.0 -f dockerfiles/generated/base/base/node-20/Dockerfile .

echo "{\"text\":\"Cykubed runner *base* images created with tag 2.1.0\"}" > slack_payload.json
/usr/bin/curl -X POST -H 'Content-type: application/json' --data "@slack_payload.json" $SLACK_HOOK_URL
