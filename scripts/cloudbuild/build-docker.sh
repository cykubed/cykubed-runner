VERSION=$(cat /workspace/version.txt)
docker build . -f dockerfiles/base/Dockerfile -t europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-base:"$VERSION"
docker build . -f dockerfiles/node16.x/Dockerfile -t europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:"$VERSION" --build-arg TAG="$VERSION"
sed "s/IMAGE_TAG/$VERSION/g" scripts/cloudbuild/payload.json > /workspace/cykube-payload.json
echo "{\"text\":\"Cykube runner $VERSION published\"}" > /workspace/slack-payload.json

