import os
import subprocess

import httpx
from loguru import logger

from common.exceptions import BuildFailedException
from common.utils import get_headers
from settings import settings


def get_async_client():
    return httpx.AsyncClient(headers=get_headers())


def runcmd(cmd: str, **kwargs):
    logger.info(cmd)
    env = os.environ.copy()
    env['PATH'] = './node_modules/.bin:' + env['PATH']
    result = subprocess.run(cmd, shell=True, capture_output=True, env=env, encoding='utf8', **kwargs)
    if result.returncode:
        raise BuildFailedException("Failed:\n"+result.stderr)


async def upload_to_cache(filepath):
    # upload to cache
    async with httpx.AsyncClient() as http:
        filename = os.path.split(filepath)[-1]
        r = await http.post(os.path.join(settings.AGENT_URL, 'upload'),
                            files={'file': (filename, open(filepath, 'rb'), 'application/octet-stream')},
                            headers={'filename': filename})
        if r.status_code != 200:
            raise BuildFailedException(f"Failed to upload {filename} to agent file cache")
