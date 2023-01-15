import os
import shlex
import subprocess

import httpx

from common.exceptions import BuildFailedException
from common.utils import get_headers
from logs import logger
from settings import settings


def get_sync_client():
    return httpx.Client(headers=get_headers())


def get_async_client():
    return httpx.AsyncClient(headers=get_headers())


def runcmd(cmd: str, **kwargs):
    env = os.environ.copy()
    env['PATH'] = './node_modules/.bin:' + env['PATH']
    env['CYPRESS_CACHE_FOLDER'] = 'cypress_cache'
    with subprocess.Popen(shlex.split(cmd), shell=True, env=env, encoding=settings.ENCODING,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          **kwargs) as proc:
        while True:
            line = proc.stdout.readline()
            if not line and proc.returncode is not None:
                break
            if line:
                logger.cmdout(line)
            proc.poll()

        if proc.returncode:
            logger.error(f"Command failed: error code {proc.returncode}")
            raise BuildFailedException()


def upload_to_cache(filepath, filename):
    # upload to cache
    r = httpx.post(os.path.join(settings.AGENT_URL, 'upload'),
                   files={'file': (filename, open(filepath, 'rb'), 'application/octet-stream')})
    if r.status_code != 200:
        logger.error(f"Failed to upload {filename} to agent file cache: {r.status_code} {r.text}")
        raise BuildFailedException()
