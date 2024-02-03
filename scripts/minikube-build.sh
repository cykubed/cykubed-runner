#!/bin/bash
set -e

REGION=europe
APITOKEN=$(mysql -sNe "select token from user where email='nick@cykubed.com'" cykubedmain)
BASETAG=$(jq -r '.base' dockerfiles/versions.json)
TAG=$(jq -r '.full' dockerfiles/versions.json)

echo "Using base tag $BASETAG and tag $TAG"

for nodever in 18 #16 18 20
do
echo "Build app Cypress image for Node $nodever"
image=$REGION-docker.pkg.dev/cykubed/public/runner/cypress-node-$nodever:$TAG
docker build -f dockerfiles/full/Dockerfile --build-arg tag=$TAG --build-arg base=cypress-base-node-$nodever:$BASETAG \
             -t $image .
echo " loading image $image"
minikube image load $image

#echo "Build app Playwright image for Node $nodever"
#image=$REGION-docker.pkg.dev/cykubed/public/runner/playwright-node-$nodever:$TAG
#docker build -f dockerfiles/full/Dockerfile --build-arg tag=$TAG --build-arg base=playwright-base-node-$nodever:$BASETAG \
#             -t $image .
#echo " loading image $image"
#minikube image load $image

done

echo "Update projects to use Electron base image"

http POST http://localhost:5002/admin/image/runner/current-version/$TAG -A bearer -a $APITOKEN
