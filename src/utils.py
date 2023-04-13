import os
import shlex
import subprocess

from httpx import AsyncClient
from loguru import logger

from common.enums import TestRunStatus
from common.exceptions import BuildFailedException
from common.redisutils import async_redis
from common.schemas import NewTestRun
from common.settings import settings
from logs import logger


def get_git_sha(testrun: NewTestRun):
    return subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=settings.get_build_dir(),
                                              text=True).strip('\n')


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


async def set_status(httpclient: AsyncClient, status: TestRunStatus):
    r = await httpclient.post(f'/status/{status}')
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to contact main server to update status to {status}: {r.status_code}: {r.text}")


async def get_testrun(id: int) -> NewTestRun | None:
    """
    Used by agents and runners to return a deserialised NewTestRun
    :param id:
    :return:
    """
    d = await async_redis().get(f'testrun:{id}')
    if d:
        return NewTestRun.parse_raw(d)
    return None
