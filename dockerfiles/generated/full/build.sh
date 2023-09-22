#!/bin/bash
set -e
docker build -t us-docker.pkg.dev/cykubed/public/base-runner:3.18.1 -f dockerfiles/base/runner/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/base-runner
docker build -t us-docker.pkg.dev/cykubed/public/node-14:3.18.1 -f dockerfiles/generated/full/node-14/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14
docker build -t us-docker.pkg.dev/cykubed/public/node-14-chrome:3.18.1 -f dockerfiles/generated/full/node-14-chrome/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-chrome
docker build -t us-docker.pkg.dev/cykubed/public/node-14-edge:3.18.1 -f dockerfiles/generated/full/node-14-edge/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-edge
docker build -t us-docker.pkg.dev/cykubed/public/node-14-firefox:3.18.1 -f dockerfiles/generated/full/node-14-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-firefox
docker build -t us-docker.pkg.dev/cykubed/public/node-14-chrome-edge-firefox:3.18.1 -f dockerfiles/generated/full/node-14-chrome-edge-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-14-chrome-edge-firefox
docker build -t us-docker.pkg.dev/cykubed/public/node-16:3.18.1 -f dockerfiles/generated/full/node-16/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-16
docker build -t us-docker.pkg.dev/cykubed/public/node-16-chrome:3.18.1 -f dockerfiles/generated/full/node-16-chrome/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-16-chrome
docker build -t us-docker.pkg.dev/cykubed/public/node-16-edge:3.18.1 -f dockerfiles/generated/full/node-16-edge/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-16-edge
docker build -t us-docker.pkg.dev/cykubed/public/node-16-firefox:3.18.1 -f dockerfiles/generated/full/node-16-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-16-firefox
docker build -t us-docker.pkg.dev/cykubed/public/node-16-chrome-edge-firefox:3.18.1 -f dockerfiles/generated/full/node-16-chrome-edge-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-16-chrome-edge-firefox
docker build -t us-docker.pkg.dev/cykubed/public/node-18:3.18.1 -f dockerfiles/generated/full/node-18/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-18
docker build -t us-docker.pkg.dev/cykubed/public/node-18-chrome:3.18.1 -f dockerfiles/generated/full/node-18-chrome/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-18-chrome
docker build -t us-docker.pkg.dev/cykubed/public/node-18-edge:3.18.1 -f dockerfiles/generated/full/node-18-edge/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-18-edge
docker build -t us-docker.pkg.dev/cykubed/public/node-18-firefox:3.18.1 -f dockerfiles/generated/full/node-18-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-18-firefox
docker build -t us-docker.pkg.dev/cykubed/public/node-18-chrome-edge-firefox:3.18.1 -f dockerfiles/generated/full/node-18-chrome-edge-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-18-chrome-edge-firefox
docker build -t us-docker.pkg.dev/cykubed/public/node-20:3.18.1 -f dockerfiles/generated/full/node-20/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-20
docker build -t us-docker.pkg.dev/cykubed/public/node-20-chrome:3.18.1 -f dockerfiles/generated/full/node-20-chrome/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-20-chrome
docker build -t us-docker.pkg.dev/cykubed/public/node-20-edge:3.18.1 -f dockerfiles/generated/full/node-20-edge/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-20-edge
docker build -t us-docker.pkg.dev/cykubed/public/node-20-firefox:3.18.1 -f dockerfiles/generated/full/node-20-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-20-firefox
docker build -t us-docker.pkg.dev/cykubed/public/node-20-chrome-edge-firefox:3.18.1 -f dockerfiles/generated/full/node-20-chrome-edge-firefox/Dockerfile .
docker push -a us-docker.pkg.dev/cykubed/public/node-20-chrome-edge-firefox

http POST https://api.cykubed.com/admin/runner/image -A bearer -a $CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
http POST $SLACK_HOOK_URL < dockerfiles/generated/full/slack-payload.json
