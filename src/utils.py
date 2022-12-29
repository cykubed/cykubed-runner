import logging
import os
import subprocess
import tempfile
import threading
import time

import httpx
from loguru import logger

from common.exceptions import BuildFailedException
from common.utils import get_headers
from settings import settings

logfile = None
logthread: threading.Thread = None
running = True


def log_watcher(trid: int, fname: str):
    global running
    with open(fname, 'r') as logfile:
        while running:
            logs = logfile.read()
            if logs:
                r = httpx.post(f'{settings.MAIN_API_URL}/agent/testrun/{trid}/logs',
                               data=logs.encode('utf8'), headers=get_headers())
                if r.status_code != 200:
                    logger.error(f"Failed to push logs")
            time.sleep(settings.LOG_UPDATE_PERIOD)


def start_log_thread(testrun_id: int):
    global logfile
    global logthread
    logfile = tempfile.NamedTemporaryFile(suffix='.log', mode='w')
    logthread = threading.Thread(target=log_watcher, args=(testrun_id, logfile.name))
    logthread.start()
    return logfile


def stop_log_thread():
    global running
    global logthread
    running = False
    logthread.join()


def get_async_client():
    return httpx.AsyncClient(headers=get_headers())


def runcmd(cmd: str, **kwargs):
    logging.info(cmd)
    global logfile
    env = os.environ.copy()
    env['PATH'] = './node_modules/.bin:' + env['PATH']
    subprocess.check_call(cmd, shell=True, stderr=logfile, stdout=logfile, env=env, **kwargs)


async def upload_to_cache(http: httpx.AsyncClient, file):
    # upload to cache
    filename = os.path.split(file.name)[-1]
    r = await http.post(os.path.join(settings.HUB_URL, '/upload'),
                        files={'file': (filename, open(file, 'rb'), 'application/octet-stream')},
                        headers={'filename': filename})
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to upload {filename} to agent file cache")
