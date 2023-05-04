IMAGE="europe-docker.pkg.dev/cykubeapp/cykubed/runner-node16.x:$1"
docker build . -f dockerfiles/base/Dockerfile -t "europe-docker.pkg.dev/cykubeapp/cykubed/runner-base:$1"
docker build . -f dockerfiles/node16.x/Dockerfile -t "$IMAGE" --build-arg TAG="$1"
minikube image load "$IMAGE"
echo "Loaded image $IMAGE"
./scripts/update-runner-images.sh $1
