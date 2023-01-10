import logging
import threading
import time
from logging import Handler, LogRecord

import httpx

from common.utils import get_headers
from settings import settings


class PublishThread(threading.Thread):
    def __init__(self, testrun_id: int, flush_period=5, *args, **kwargs):
        super().__init__(daemon=True, *args, **kwargs)
        self.buffer = []
        self.period = flush_period
        self.testrun_id = testrun_id
        self.running = True

    def add(self, record: LogRecord):
        self.buffer.append(record)

    def run(self) -> None:
        while self.running:
            try:
                time.sleep(self.period)
                if len(self.buffer):
                    payload = "\n".join([x.msg for x in self.buffer]) + '\n'
                    httpx.post(f'{settings.MAIN_API_URL}/agent/testrun/{self.testrun_id}/logs',
                               content=payload, headers=get_headers())
                    self.buffer.clear()
            except Exception as ex:
                logging.error(f"Failed to post logs: {ex}")


class PublishLogHandler(Handler):

    def __init__(self, testrun_id: int, flush_period=5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.testrun_id = testrun_id
        self.publish_thread = PublishThread(testrun_id, flush_period)
        self.publish_thread.start()

    def emit(self, record: LogRecord) -> None:
        # flush, using a thread
        self.publish_thread.add(record)

    def close(self) -> None:
        super().close()
        self.publish_thread.running = False
        self.publish_thread.join(timeout=10)

