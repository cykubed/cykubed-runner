IMAGE="europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:$1"
docker build . -f dockerfiles/base/Dockerfile -t "europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-base:$1"
docker build . -f dockerfiles/node16.x/Dockerfile -t "$IMAGE" --build-arg TAG="$1"
minikube image load "$IMAGE"
echo "Loaded image $IMAGE"
./scripts/update-runner-images.sh $1
