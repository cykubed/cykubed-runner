IMAGE="ghcr.io/cykubed/runner"
TAG=5.0.0

for nodever in 20 #18 16
do
echo "Build Cypress image for Node $nodever"
docker build -f dockerfiles/full/Dockerfile --build-arg base=ghcr.io/cykubed/base-runner-cypress-$nodever:$TAG -t ghcr.io/cykubed/runner-cypress-$nodever:$TAG .

echo "Build Playwright image for Node $nodever"
docker build -f dockerfiles/full/Dockerfile --build-arg base=ghcr.io/cykubed/base-runner-playwright-$nodever:$TAG -t ghcr.io/cykubed/runner-playwright-$nodever:$TAG .

done
