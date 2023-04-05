VERSION=$(cat /workspace/version.txt)
docker push europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-base:"$VERSION"
docker push europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:"$VERSION"

