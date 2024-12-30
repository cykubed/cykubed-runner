#!/bin/bash
set -e

IMAGE="ghcr.io/cykubed/base-runner"
BASETAG=$(jq -r '.base' dockerfiles/versions.json)

echo "Using base tag $BASETAG"

echo "Build base Cypress image"
docker build -f dockerfiles/base/cypress/Dockerfile -t $IMAGE-base:$BASETAG .

for nodever in 20 18 16
do
echo "Build base Cypress image for Node $nodever"
docker build -f dockerfiles/base/node/Dockerfile --build-arg node=$nodever --build-arg base=$IMAGE-base:$BASETAG -t $IMAGE-cypress-$nodever:$BASETAG .

echo "Build base Playwright image for Node $nodever"
docker build -f dockerfiles/base/playwright/Dockerfile --build-arg node=$nodever -t $IMAGE-playwright-$nodever:$BASETAG .

done
