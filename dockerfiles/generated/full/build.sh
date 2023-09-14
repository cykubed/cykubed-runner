#!/bin/bash
set -e
docker build -t us-docker.pkg.dev/cykubed/public/node-14:3.0.1 -f dockerfiles/generated/full/node-14/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-14-chrome:3.0.1 -f dockerfiles/generated/full/node-14-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-14-edge:3.0.1 -f dockerfiles/generated/full/node-14-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-14-firefox:3.0.1 -f dockerfiles/generated/full/node-14-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-14-chrome-edge-firefox:3.0.1 -f dockerfiles/generated/full/node-14-chrome-edge-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16:3.0.1 -f dockerfiles/generated/full/node-16/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-chrome:3.0.1 -f dockerfiles/generated/full/node-16-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-edge:3.0.1 -f dockerfiles/generated/full/node-16-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-firefox:3.0.1 -f dockerfiles/generated/full/node-16-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-16-chrome-edge-firefox:3.0.1 -f dockerfiles/generated/full/node-16-chrome-edge-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18:3.0.1 -f dockerfiles/generated/full/node-18/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18-chrome:3.0.1 -f dockerfiles/generated/full/node-18-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18-edge:3.0.1 -f dockerfiles/generated/full/node-18-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18-firefox:3.0.1 -f dockerfiles/generated/full/node-18-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-18-chrome-edge-firefox:3.0.1 -f dockerfiles/generated/full/node-18-chrome-edge-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20:3.0.1 -f dockerfiles/generated/full/node-20/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20-chrome:3.0.1 -f dockerfiles/generated/full/node-20-chrome/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20-edge:3.0.1 -f dockerfiles/generated/full/node-20-edge/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20-firefox:3.0.1 -f dockerfiles/generated/full/node-20-firefox/Dockerfile .
docker build -t us-docker.pkg.dev/cykubed/public/node-20-chrome-edge-firefox:3.0.1 -f dockerfiles/generated/full/node-20-chrome-edge-firefox/Dockerfile .

http POST http://localhost:5002/admin/runner/image -A bearer -a $CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
http POST $SLACK_HOOK_URL < dockerfiles/generated/full/slack-payload.json
