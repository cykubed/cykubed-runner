eval $(minikube docker-env)
./scripts/build-docker.sh $1
mysql cykubemain < scripts/runner-images.sql

