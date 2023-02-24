docker build . -f dockerfiles/base/Dockerfile -t nickbrookck/cykube-runner:base-$1
docker build . -f dockerfiles/chrome/Dockerfile -t nickbrookck/cykube-runner:chrome90-$1 --build-arg TAG=$1
docker build . -f dockerfiles/chrome-node16.13.0/Dockerfile -t nickbrookck/cykube-runner:chrome90-node16.13-$1 --build-arg TAG=$1
docker build . -f dockerfiles/chrome-node16.x/Dockerfile -t nickbrookck/cykube-runner:chrome90-node16.x-$1 --build-arg TAG=$1

docker push nickbrookck/cykube-runner:base-$1
docker push nickbrookck/cykube-runner:chrome90-$1
docker push nickbrookck/cykube-runner:chrome90-node16.13-$1
docker push nickbrookck/cykube-runner:chrome90-node16.x-$1



