import queue
import sys
import threading
import time
from logging import Handler, LogRecord

import httpx
from loguru import logger

from common.utils import get_headers
from settings import settings


class PublishThread(threading.Thread):
    def __init__(self, testrun_id: int, *args, **kwargs):
        super().__init__(daemon=True, *args, **kwargs)
        self.q = queue.Queue()
        self.testrun_id = testrun_id

    def add(self, logs):
        self.q.put(logs)

    def run(self) -> None:
        while True:
            logs = self.q.get()
            httpx.post(f'{settings.MAIN_API_URL}/agent/testrun/{self.testrun_id}/logs',
                           data=logs, headers=get_headers())
            self.q.task_done()


class PublishLogHandler(Handler):

    def handle(self, record: LogRecord) -> bool:
        return super().handle(record)

    def __init__(self, testrun_id: int, flush_period=5, max_buffer=100, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = []
        self.testrun_id = testrun_id
        self.last_time = None
        self.flush_period = flush_period
        self.max_buffer = max_buffer
        self.publish_thread = PublishThread(testrun_id)
        self.publish_thread.start()

    def emit(self, record: LogRecord) -> None:
        self.buffer.append(record)
        now = time.time()
        if self.last_time is None:
            self.last_time = now

        since_last = now - self.last_time
        if len(self.buffer) > self.max_buffer or since_last > self.flush_period:
            # flush, using a thread
            self.publish_thread.add(self.buffer)
            self.buffer.clear()


def configure(testrun_id: int):
    fmt = "{time:HH:mm:ss} {level} {message}"
    logger.add(PublishLogHandler(testrun_id, settings.LOG_UPDATE_PERIOD),
               level='DEBUG', format=fmt, serialize=True)
