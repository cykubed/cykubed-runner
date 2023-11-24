import os
import shlex
import subprocess
import traceback

import loguru
from httpx import Client

from cykubedrunner.app import app
from cykubedrunner.common import schemas
from cykubedrunner.common.enums import TestRunStatus, loglevelToInt, LogLevel, AgentEventType
from cykubedrunner.common.exceptions import BuildFailedException
from cykubedrunner.common.redisutils import sync_redis
from cykubedrunner.common.schemas import NewTestRun, AgentEvent, AppLogMessage, AgentTestRunErrorEvent, \
    TestRunErrorReport
from cykubedrunner.common.utils import utcnow
from cykubedrunner.settings import settings


def get_git_sha(testrun: NewTestRun):
    return subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=settings.BUILD_DIR,
                                              text=True).strip('\n')


def get_env_and_args(args: str, node=False, **kwargs):
    cmdenv = os.environ.copy()
    cmdenv['CYPRESS_CACHE_FOLDER'] = f'{settings.BUILD_DIR}/cypress_cache'
    if 'path' in kwargs:
        cmdenv['PATH'] = kwargs['path']+':'+cmdenv['PATH']
    else:
        cmdenv['PATH'] = f'{settings.src_dir}/node_modules/.bin:' + os.environ['PATH']
    if node and app.is_yarn and not args.startswith('yarn '):
        args = f'yarn run {args}'
    return cmdenv, args


def runcmd(args: str, cmd=False, env=None, log=False, node=False, **kwargs):
    cmdenv, args = get_env_and_args(args, node, **kwargs)

    if env:
        cmdenv.update(env)

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
    if settings.LOCAL_REDIS:
        d = sync_redis().get(f'testrun:{id}')
        if d:
            return NewTestRun.parse_raw(d)
    else:
        r = app.http_client.get('')
        if r.status_code != 200:
            raise BuildFailedException(f"Failed to fetch testrun")
        return r.json()
    return None


def send_agent_event(event: AgentEvent):
    if settings.LOCAL_REDIS:
        sync_redis().rpush('messages', event.json())
    else:
        r = app.http_client.post('/event', json=event.json())
        if r.status_code != 200:
            raise BuildFailedException('Failed to send event to server')


def log_build_failed_exception(trid: int, ex: BuildFailedException):
    # tell the agent
    app.http_client.post('/error', json=AgentTestRunErrorEvent(testrun_id=trid,
                                            report=TestRunErrorReport(msg=ex.msg,
                                                                      stage=ex.stage,
                                                                      error_code=ex.status_code)).json())


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
            r = app.http_client.post('/log', json=event.json())
            if r.status_code != 200:
                loguru.logger.warning('Failed to send log message')

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


def get_node_version() -> str:
    return runcmd('node --version').stdout.strip()


logger = TestRunLogger()


def root_file_exists(name):
    return os.path.exists(os.path.join(settings.src_dir, name))
