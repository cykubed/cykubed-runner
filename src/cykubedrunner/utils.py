import os
import shlex
import subprocess
import traceback

import loguru
from common import schemas
from common.enums import TestRunStatus, loglevelToInt, LogLevel, AgentEventType
from common.exceptions import BuildFailedException
from common.redisutils import sync_redis
from common.schemas import NewTestRun, AgentEvent, AppLogMessage
from common.utils import utcnow
from httpx import Client
from loguru import logger

from app import app
from settings import settings


def get_git_sha(testrun: NewTestRun):
    return subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=settings.BUILD_DIR,
                                              text=True).strip('\n')


def runcmd(args: str, cmd=False, env=None, log=False, node=False, **kwargs):
    cmdenv = os.environ.copy()
    cmdenv['CYPRESS_CACHE_FOLDER'] = f'{settings.BUILD_DIR}/cypress_cache'
    if 'path' in kwargs:
        cmdenv['PATH'] = kwargs['path']+':'+cmdenv['PATH']
    else:
        cmdenv['PATH'] = f'{settings.src_dir}/node_modules/.bin:' + os.environ['PATH']
    if env:
        cmdenv.update(env)

    if node and app.is_yarn and not args.startswith('yarn '):
        args = f'yarn run {args}'

    result = None
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
    os.sync()
    return result


def set_status(httpclient: Client, status: TestRunStatus):
    r = httpclient.post(f'/status/{status}')
    if r.status_code != 200:
        raise BuildFailedException(f"Failed to contact main server to update status to {status}: {r.status_code}: {r.text}")


def get_testrun(id: int) -> NewTestRun | None:
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


class TestRunLogger:
    def __init__(self):
        self.testrun_id = None
        self.source = None
        self.step = 0
        self.level = loglevelToInt[LogLevel.info]

    def init(self, testrun_id: int, source: str, level: LogLevel = LogLevel.info):
        self.testrun_id = testrun_id
        self.source = source
        self.level = loglevelToInt[level]

    def log(self, msg: str, level: LogLevel):
        if level == LogLevel.cmd:
            loguru_level = 'info'
        elif level == LogLevel.cmdout:
            loguru_level = 'debug'
        else:
            loguru_level = level.name

        if msg.strip('\n'):
            loguru.logger.log(loguru_level.upper(), msg.strip('\n'))

        if loglevelToInt[level] < self.level:
            return
        # post to the agent
        if self.testrun_id:
            event = schemas.AgentLogMessage(type=AgentEventType.log,
                                            testrun_id=self.testrun_id,
                                            msg=AppLogMessage(
                                                ts=utcnow(),
                                                level=level,
                                                host=app.hostname,
                                                msg=msg,
                                                step=self.step,
                                                source=self.source))
            send_agent_event(event)

    def cmd(self, msg: str):
        self.step += 1
        self.log(msg, LogLevel.cmd)

    def cmdout(self, msg: str):
        self.log(msg, LogLevel.cmdout)

    def debug(self, msg: str):
        self.log(msg, LogLevel.debug)

    def info(self, msg: str):
        self.log(msg, LogLevel.info)

    def warning(self, msg: str):
        self.log(msg, LogLevel.warning)

    def error(self, msg: str):
        self.log(msg, LogLevel.error)

    def exception(self, msg):
        self.log(str(msg) + '\n' + traceback.format_exc() + '\n', LogLevel.error)


def increase_duration(testrun_id, cmd: str, duration: int):
    if not app.is_spot:
        sync_redis().incrby(f'testrun:{testrun_id}:{cmd}:duration:normal', duration)
    else:
        sync_redis().incrby(f'testrun:{testrun_id}:{cmd}:duration:spot', duration)


logger = TestRunLogger()


def root_file_exists(name):
    return os.path.exists(os.path.join(settings.src_dir, name))
