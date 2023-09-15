docker build -t $region-docker.pkg.dev/cykubed/public/$path:$tag -f dockerfiles/generated/full/$path/Dockerfile .
docker push -a $region-docker.pkg.dev/cykubed/public/$path
