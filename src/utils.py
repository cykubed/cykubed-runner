import logging
import os
import subprocess

import httpx

import common.logupload
from common.exceptions import BuildFailedException
from common.utils import get_headers
from settings import settings


def get_async_client():
    return httpx.AsyncClient(headers=get_headers())


def runcmd(cmd: str, **kwargs):
    logging.info(cmd)
    env = os.environ.copy()
    env['PATH'] = './node_modules/.bin:' + env['PATH']
    subprocess.check_call(cmd, shell=True, stderr=common.logupload.logfile, stdout=common.logupload.logfile, env=env, **kwargs)


async def upload_to_cache(file):
    # upload to cache
    async with httpx.AsyncClient() as http:
        filename = os.path.split(file.name)[-1]
        r = await http.post(os.path.join(settings.AGENT_URL, 'upload'),
                            files={'file': (filename, open(file, 'rb'), 'application/octet-stream')},
                            headers={'filename': filename})
        if r.status_code != 200:
            raise BuildFailedException(f"Failed to upload {filename} to agent file cache")
