import os
import shlex
import subprocess

from common.exceptions import BuildFailedException
from common.schemas import NewTestRun
from common.settings import settings
from httpclient import get_sync_client
from logs import logger


def runcmd(args: str, cmd=False, env=None, log=False, **kwargs):
    cmdenv = os.environ.copy()
    cmdenv['PATH'] = './node_modules/.bin:' + cmdenv['PATH']
    cmdenv['CYPRESS_CACHE_FOLDER'] = 'cypress_cache'
    if env:
        cmdenv.update(env)

    if not cmd:
        result = subprocess.run(args, env=cmdenv, shell=True, encoding=settings.ENCODING, capture_output=True,
                                **kwargs)
        if log:
            logger.debug(args)
        if result.returncode:
            logger.error(f"Command failed: {result.returncode}: {result.stderr}")
            raise BuildFailedException()
    else:
        logger.cmd(args)
        with subprocess.Popen(shlex.split(args), env=cmdenv, encoding=settings.ENCODING,
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
    files = {'file': (filename, open(filepath, 'rb'), 'application/octet-stream')}
    resp = get_sync_client().post(os.path.join(settings.AGENT_URL, 'upload'), files=files)
    if resp.status_code != 200:
        raise BuildFailedException(f"Failed to upload {filename} to agent file cache")


def fetch_testrun(testrun_id: int) -> NewTestRun:
    # we'll need the test run from the agent
    try:
        resp = get_sync_client().get(f'{settings.AGENT_URL}/testrun/{testrun_id}')
        if resp.status_code != 200:
            raise BuildFailedException(f"Failed to fetch test run from agent ({resp.status_code}): quitting")

        return NewTestRun.parse_raw(resp.text)
    except:
        raise BuildFailedException("Failed to fetch test run from agent: quitting")
