docker build . -f dockerfiles/base/Dockerfile -t nickbrookck/cykube-runner:base-$1
docker build . -f dockerfiles/node16.x/Dockerfile -t nickbrookck/cykube-runner:node16.x-$1 --build-arg TAG=$1


