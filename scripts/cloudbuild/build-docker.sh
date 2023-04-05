docker build . -f dockerfiles/base/Dockerfile -t europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-base:$1
docker build . -f dockerfiles/node16.x/Dockerfile -t europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:$1 --build-arg TAG=$1
sed "s/IMAGE_TAG/$1/g" scripts/cloudbuild/payload.json > /workspace/cykube-payload.json
echo "{\"text\":\"Cykube runner $1 published\"}" > /workspace/slack-payload.json

