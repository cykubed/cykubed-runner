export AGENT_URL=https://dev.cykube.net/test-agent
export API_TOKEN=8de9c347-d8a4-46ca-879b-41673094f0d2
export BUILD_DIR=/tmp/cykube/build
export CACHE_URL=https://dev.cykube.net/test-cache
export FILESTORE_SERVERS=https://dev.cykube.net/fs1
export K8=false
export MAIN_API_URL=https://dev.cykube.net/api
export NODE_PATH=/home/nick/.nvm/versions/node/v16.18.1/bin
export PYTHONPATH=src:.
python src/main.py run $1
