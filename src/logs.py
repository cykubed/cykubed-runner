import traceback
from datetime import datetime

import loguru

from common import schemas
from common.enums import LogLevel, loglevelToInt, AgentEventType
from common.redisutils import sync_redis
from common.schemas import AppLogMessage


class TestRunLogger:
    def __init__(self):
        self.testrun_id = None
        self.source = None
        self.step = 0
        self.level = loglevelToInt[LogLevel.info]
        self.redis_client = sync_redis()

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
                                                ts=datetime.now(),
                                                level=level,
                                                msg=msg,
                                                step=self.step,
                                                source=self.source))
            self.redis_client.rpush('messages', event.json())

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


logger = TestRunLogger()
