import os

# default build timeout, in seconds
BUILD_TIMEOUT: int = os.environ.get('BUILD_TIMEOUT', 30*60)

