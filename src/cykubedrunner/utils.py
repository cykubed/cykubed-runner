import os
import shlex
import subprocess
import sys
import traceback

import httpx
import loguru
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_fixed, wait_random

from cykubedrunner.app import app
from cykubedrunner.common import schemas
from cykubedrunner.common.enums import loglevelToInt, LogLevel, AgentEventType
from cykubedrunner.common.exceptions import BuildFailedException, RunFailedException
from cykubedrunner.common.schemas import NewTestRun, AgentEvent, AppLogMessage, TestRunErrorReport, SpecTests, \
    AgentSpecCompleted
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


def send_agent_event(event: AgentEvent):
    r = app.post('/event', content=event.json())
    if r.status_code != 200:
        raise BuildFailedException('Failed to send event to server')


def log_build_failed_exception(ex: BuildFailedException):
    # tell the agent
    app.post('error',
             content=TestRunErrorReport(msg=ex.msg, stage=ex.stage, error_code=ex.status_code).json())


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
        # post to the server
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
            if settings.AGENT_URL:
                # via the agent websocket
                r = httpx.post(f'{settings.AGENT_URL}/log', content=event.json())
            else:
                # direct to the server
                r = app.post('log', content=event.json())
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


@retry(retry=retry_if_not_exception_type(RunFailedException),
       stop=stop_after_attempt(settings.MAX_HTTP_RETRIES if not settings.TEST else 1),
       wait=wait_fixed(2) + wait_random(0, 4))
def upload_files(files) -> list[str]:
    resp = app.post('upload-artifacts', files=files)
    return resp.json()['urls']


def all_results_with_screenshots_generator(specresult: SpecTests):
    for test in specresult.tests:
        for result in test.results:
            if result.failure_screenshots:
                yield result


def upload_results(spec: str, specresult: SpecTests):
    files = []

    for result in all_results_with_screenshots_generator(specresult):
        for sshot in result.failure_screenshots:
            files.append(('files', open(sshot, 'rb')))

    if files:
        urls = upload_files(files)
        for result in all_results_with_screenshots_generator(specresult):
            num = len(result.failure_screenshots)
            result.failure_screenshots = urls[:num]
            urls = urls[num:]

    msg = AgentSpecCompleted(
        result=specresult,
        file=spec,
        finished=utcnow())

    logger.debug(f'Uploading results: {msg.json()}')

    if specresult.video:
        urls = upload_files([('files', open(specresult.video, 'rb'))])
        msg.video = urls[0]

    app.post('spec-completed', content=msg.json())


def default_sigterm_runner(signum, frame):
    """
    Default behaviour is just to log and quit with error code
    """
    logger.warning(f"SIGTERM/SIGINT caught: bailing out")
    sys.exit(1)


