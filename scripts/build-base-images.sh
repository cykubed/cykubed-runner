#!/bin/bash
set -e

REGION=us
BASETAG=$(jq -r '.base' dockerfiles/versions.json)

echo "Using base tag $BASETAG"

echo "Build base Cypress image"
docker build -f dockerfiles/base/cypress/Dockerfile -t $REGION-docker.pkg.dev/cykubed/public/runner/cypress-base:$BASETAG .


for nodever in 16 18 20
do
echo "Build base Cypress image for Node $nodever"
docker build -f dockerfiles/base/node/Dockerfile --build-arg node=$nodever --build-arg basetag=cypress-base:$BASETAG -t $REGION-docker.pkg.dev/cykubed/public/runner/cypress-base-node-$nodever:$BASETAG .
done
