#!/bin/bash
set -e
docker build -t us-docker.pkg.dev/cykubed/public/base-runner:3.14.0 -f dockerfiles/base/runner/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/base-runner
docker build -t us-docker.pkg.dev/cykubed/public/node-14:3.14.0 -f dockerfiles/generated/full/node-14/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14
docker build -t us-docker.pkg.dev/cykubed/public/node-14-chrome:3.14.0 -f dockerfiles/generated/full/node-14-chrome/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-chrome

http POST https://api.cykubed.com/admin/runner/image -A bearer -a $CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
http POST $SLACK_HOOK_URL < dockerfiles/generated/full/slack-payload.json
