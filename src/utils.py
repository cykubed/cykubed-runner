import os
import shlex
import subprocess

from httpx import Client
from loguru import logger

from common.enums import TestRunStatus
from common.exceptions import BuildFailedException
from common.redisutils import sync_redis
from common.schemas import NewTestRun, AgentTestRun, AgentEvent
from logs import logger
from settings import settings


def get_git_sha(testrun: NewTestRun):
    return subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=settings.BUILD_DIR,
                                              text=True).strip('\n')


def runcmd(args: str, cmd=False, env=None, log=False, **kwargs):
    cmdenv = os.environ.copy()
    cmdenv['PATH'] = f'{settings.NODE_CACHE_DIR}/node_modules/.bin:' + cmdenv['PATH']
    cmdenv['CYPRESS_CACHE_FOLDER'] = f'{settings.NODE_CACHE_DIR}/cypress_cache'
    if env:
        cmdenv.update(env)

    if not cmd:
        result = subprocess.run(args, env=cmdenv, shell=True, encoding=settings.ENCODING, capture_output=True,
                                **kwargs)
        if log:
            logger.debug(args)
        if result.returncode:
            logger.error(f"Command failed: {result.returncode}: {result.stderr}")
            raise BuildFailedException(msg=f'Command failed: {result.stderr}', status_code=result.returncode)
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
                raise BuildFailedException(msg='Command failed', status_code=proc.returncode)


def set_status(httpclient: Client, status: TestRunStatus):
    r = httpclient.post(f'/status/{status}')
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to contact main server to update status to {status}: {r.status_code}: {r.text}")


def get_testrun(id: int) -> AgentTestRun | None:
    """
    Used by agents and runners to return a deserialised NewTestRun
    :param id:
    :return:
    """
    d = sync_redis().get(f'testrun:{id}')
    if d:
        return NewTestRun.parse_raw(d)
    return None


def send_agent_event(event: AgentEvent):
    sync_redis().rpush('messages', event.json())
