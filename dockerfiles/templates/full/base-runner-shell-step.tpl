docker build -t $region-docker.pkg.dev/cykubed/public/base-runner:$tag -f dockerfiles/base/runner/Dockerfile .
docker push -a $region-docker.pkg.dev/cykubed/public/base-runner

