#!/bin/bash
set -e
python dockerfiles/release.py -g -b patch -n "Local build"

APITOKEN=$(mysql -sNe "select token from user limit 1" cykubedmain)
BASETAG=$(jq -r '.[0].image' dockerfiles/generated/full/cykubed-payload.json | sed 's/:/\n/g' | tail -n 1
)


TAG=${1:-$BASETAG}

echo "Using base tag $TAG"

BASE_RUNNER_IMAGE="us-docker.pkg.dev/cykubed/public/node-18:$TAG"

echo "Build images"

head -n 3 dockerfiles/generated/full/build.sh | sh
grep node-16 dockerfiles/generated/full/build.sh | head -n 3 | sh
grep node-18 dockerfiles/generated/full/build.sh | head -n 3 | sh

echo "Load images into Minikube"

minikube image load us-docker.pkg.dev/cykubed/public/node-16:$TAG &
minikube image load us-docker.pkg.dev/cykubed/public/node-16-chrome:$TAG &
minikube image load us-docker.pkg.dev/cykubed/public/node-18:$TAG &
minikube image load us-docker.pkg.dev/cykubed/public/node-18-chrome:$TAG &

echo "Update projects to use Electron base image"

http POST http://localhost:5002/admin/docker/image -A bearer -a $APITOKEN  < dockerfiles/generated/full/cykubed-payload.json
