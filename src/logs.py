import traceback
from datetime import datetime
from logging import Handler, LogRecord

import httpx

from common import schemas
from common.enums import LogLevel
from settings import settings


class PublishLogHandler(Handler):

    def __init__(self, project_id: int, local_id: int, source: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_id = project_id
        self.local_id = local_id
        self.source = source

    def emit(self, record: LogRecord) -> None:
        # post to the agent
        msg = schemas.AgentLogMessage(ts=datetime.fromtimestamp(record.created),
                                                project_id=self.project_id,
                                                local_id=self.local_id,
                                                level=record.levelname.lower(),
                                                msg=record.msg,
                                                source=self.source)
        httpx.post(f'{settings.AGENT_URL}/log', data=msg.json())


class Logger:
    def __init__(self, project_id: int, local_id: int, source: str):
        self.project_id = project_id
        self.local_id = local_id
        self.source = source
        self.step = 0

    def log(self, msg: str, level: LogLevel):
        # post to the agent
        msg = schemas.AgentLogMessage(ts=datetime.now(),
                                      project_id=self.project_id,
                                      local_id=self.local_id,
                                      level=level,
                                      msg=msg,
                                      step=self.step,
                                      source=self.source)
        httpx.post(f'{settings.AGENT_URL}/log', data=msg.json())

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

    def exception(self, msg: str):
        self.log(msg+'\n'+traceback.format_exc()+'\n', LogLevel.error)


logger = None
