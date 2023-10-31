#!/bin/bash
set -e
python dockerfiles/release.py -g -b patch -n "Local build"

APITOKEN=$(mysql -sNe "select token from user limit 1" cykubedmain)
BASETAG=$(jq -r '.[0].tag' dockerfiles/generated/full/cykubed-payload.json)

TAG=${1:-$BASETAG}

BASE_RUNNER_IMAGE="us-docker.pkg.dev/cykubed/public/node-16:$TAG"

echo "Build images"

head -n 3 dockerfiles/generated/full/build.sh | sh
grep node-18 dockerfiles/generated/full/build.sh | head -n 3 | sh

echo "Load images"

minikube image load us-docker.pkg.dev/cykubed/public/node-18:$TAG
#minikube image load us-docker.pkg.dev/cykubed/public/node-16-firefox:$TAG

echo "Update projects to use Electron base image"

http POST http://localhost:5002/admin/runner/image -A bearer -a $APITOKEN  < dockerfiles/generated/full/cykubed-payload.json

VERSIONID=$(mysql -sNe "select id from runner_image where image='us-docker.pkg.dev/cykubed/public/node-18' and archived=0" cykubedmain)

mysql cykubedmain -e "update project set runner_image=\"$BASE_RUNNER_IMAGE\", public_image_id=$VERSIONID"
