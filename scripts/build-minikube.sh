eval $(minikube docker-env)
docker build . -f dockerfiles/base/Dockerfile -t "europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-base:$1"
docker build . -f dockerfiles/node16.x/Dockerfile -t "europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:$1" --build-arg TAG="$1"
./scripts/update-runner-images.sh $1
