import os
import subprocess

import httpx
from loguru import logger

from common.exceptions import BuildFailedException
from common.utils import get_headers
from settings import settings


def get_sync_client():
    return httpx.Client(headers=get_headers())


def get_async_client():
    return httpx.AsyncClient(headers=get_headers())


def runcmd(cmd: str, **kwargs):
    env = os.environ.copy()
    env['PATH'] = './node_modules/.bin:' + env['PATH']
    env['CYPRESS_CACHE_FOLDER'] = 'cypress_cache'
    result = subprocess.run(cmd, shell=True, capture_output=True, env=env, encoding='utf8', **kwargs)
    if result.returncode:
        logger.error(result.stderr)
        raise BuildFailedException()


def upload_to_cache(filepath, filename):
    # upload to cache
    r = httpx.post(os.path.join(settings.AGENT_URL, 'upload'),
                    files={'file': (filename, open(filepath, 'rb'), 'application/octet-stream')})
    if r.status_code != 200:
        logger.error(f"Failed to upload {filename} to agent file cache: {r.status_code} {r.text}")
        raise BuildFailedException()
