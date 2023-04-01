export AGENT_URL=https://dev.cykube.net/test-agent
export BUILD_DIR=/tmp/cykube/build
export CACHE_URL=https://dev.cykube.net/test-cache
export FILESTORE_SERVERS=https://dev.cykube.net/fs1
export K8=false
export MAIN_API_URL=https://dev.cykube.net/api
export NODE_PATH=/home/nick/.nvm/versions/node/v16.18.1/bin
export PYTHONPATH=src:.
python src/main.py run $1
