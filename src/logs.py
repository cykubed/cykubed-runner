import traceback
from datetime import datetime

import httpx

from common import schemas
from common.enums import LogLevel, loglevelToInt
from common.settings import settings
import loguru


class Logger:
    def __init__(self):
        self.project_id = None
        self.local_id = None
        self.source = None
        self.step = 0
        self.level = loglevelToInt[LogLevel.info]

    def init(self, project_id: int, local_id: int, source: str, level: LogLevel = LogLevel.info):
        self.project_id = project_id
        self.local_id = local_id
        self.source = source
        self.level = loglevelToInt[level]

    def log(self, msg: str, level: LogLevel):
        if level == LogLevel.cmd:
            loguru_level = 'info'
        elif level == LogLevel.cmdout:
            loguru_level = 'debug'
        else:
            loguru_level = level.name
        loguru.logger.log(loguru_level.upper(), msg)

        if loglevelToInt[level] < self.level:
            return
        # post to the agent
        if self.project_id:
            event = schemas.AgentLogMessage(ts=datetime.now(),
                                            project_id=self.project_id,
                                            local_id=self.local_id,
                                            level=level,
                                            msg=msg,
                                            step=self.step,
                                            source=self.source)
            httpx.post(f'{settings.AGENT_URL}/log', data=event.json())

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


logger = Logger()
