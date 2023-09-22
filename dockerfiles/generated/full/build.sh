#!/bin/bash
set -e
docker build -t us-docker.pkg.dev/cykubed/public/base-runner:3.18.4 -f dockerfiles/base/runner/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/base-runner
docker build -t us-docker.pkg.dev/cykubed/public/node-16:3.18.4 -f dockerfiles/generated/full/node-16/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-16
docker build -t us-docker.pkg.dev/cykubed/public/node-16-firefox:3.18.4 -f dockerfiles/generated/full/node-16-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-16-firefox

http POST https://api.cykubed.com/admin/runner/image -A bearer -a $CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
http POST $SLACK_HOOK_URL < dockerfiles/generated/full/slack-payload.json
