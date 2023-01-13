from datetime import datetime
from logging import Handler, LogRecord

import httpx

from common import schemas
from settings import settings


class PublishLogHandler(Handler):

    def __init__(self, project_id: int, local_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_id = project_id
        self.local_id = local_id

    def emit(self, record: LogRecord) -> None:
        # post to the agent
        msg = schemas.AgentLogMessage(ts=datetime.fromtimestamp(record.created),
                                                project_id=self.project_id,
                                                local_id=self.local_id,
                                                level=record.levelname.lower(),
                                                msg=record.msg,
                                                source='runner')
        httpx.post(f'{settings.AGENT_URL}/log', data=msg.json())
