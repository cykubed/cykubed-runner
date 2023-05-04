VERSION=$(cat /workspace/version.txt)

docker build . -f dockerfiles/base/Dockerfile \
                -t europe-docker.pkg.dev/cykubeapp/cykubed/runner-base:"$VERSION" \
                -t europe-docker.pkg.dev/cykubeapp/cykubed/runner-base:latest \
                --cache-from europe-docker.pkg.dev/cykubeapp/cykubed/runner-base:latest

docker build . -f dockerfiles/node16.x/Dockerfile \
                -t europe-docker.pkg.dev/cykubeapp/cykubed/runner-node16.x:"$VERSION" \
                -t europe-docker.pkg.dev/cykubeapp/cykubed/runner-node16.x:latest \
                --cache-from europe-docker.pkg.dev/cykubeapp/cykubed/runner-node16.x:latest \
                --build-arg TAG="$VERSION"

sed "s/IMAGE_TAG/$VERSION/g" scripts/cloudbuild/payload.json > /workspace/cykube-payload.json
echo "{\"text\":\"Cykubed runner $VERSION published\"}" > /workspace/slack-payload.json

