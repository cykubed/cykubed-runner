#poetry export -o requirements.txt
eval "$(minikube docker-env)"
docker build . -f dockerfiles/base/Dockerfile -t nickbrookck/cykube-runner:base
docker build . -f dockerfiles/chrome/Dockerfile -t nickbrookck/cykube-runner:chrome-base
docker build . -f dockerfiles/node16.13.0/Dockerfile -t nickbrookck/cykube-runner:chrome-16.13.0
docker build . -f dockerfiles/node16.x/Dockerfile -t nickbrookck/cykube-runner:chrome-16.x

mysql cykubemain < "delete from runnerimage"



