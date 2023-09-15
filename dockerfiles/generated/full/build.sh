#!/bin/bash
set -e
docker build -t us-docker.pkg.dev/cykubed/public/node-14:3.0.1 -f dockerfiles/generated/full/node-14/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14
docker build -t us-docker.pkg.dev/cykubed/public/node-14-chrome:3.0.1 -f dockerfiles/generated/full/node-14-chrome/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-chrome
docker build -t us-docker.pkg.dev/cykubed/public/node-14-edge:3.0.1 -f dockerfiles/generated/full/node-14-edge/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-edge
docker build -t us-docker.pkg.dev/cykubed/public/node-14-chrome-edge-firefox:3.0.1 -f dockerfiles/generated/full/node-14-chrome-edge-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-chrome-edge-firefox

http POST http://localhost:5002/admin/runner/image -A bearer -a $CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
http POST $SLACK_HOOK_URL < dockerfiles/generated/full/slack-payload.json
