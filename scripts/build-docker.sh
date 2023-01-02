poetry export -o requirements.txt
eval "$(minikube docker-env)"
docker build . -t cykube/runner:$1


