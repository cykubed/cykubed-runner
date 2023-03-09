eval $(minikube docker-env)
./scripts/build-docker.sh $1
./scripts/update-runner-images.sh $1
