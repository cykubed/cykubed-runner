import os

import httpx

from cykubedrunner.common.exceptions import RunFailedException
from cykubedrunner.common.schemas import NewTestRun
from cykubedrunner.settings import settings


class App(object):
    def __init__(self):
        self.is_spot = False
        self.is_yarn = os.path.exists(os.path.join(settings.src_dir, 'yarn.lock'))
        self.is_yarn_modern = False
        self.is_yarn_zero_install = False
        self.is_terminating = False
        self.specs_completed = set()
        self.http_client: httpx.Client = None
        self.trid = None

        with open('/etc/hostname') as f:
            self.hostname = f.read().strip()

    def init_http_client(self, trid: int):
        self.trid = trid
        transport = httpx.HTTPTransport(retries=settings.MAX_HTTP_RETRIES)
        self.http_client = httpx.Client(transport=transport,
                                   base_url=settings.MAIN_API_URL + f'/agent',
                                   headers={'Authorization': f'Bearer {settings.API_TOKEN}'})

    def get_testrun(self) -> NewTestRun:
        r = self.http_client.get(f'testrun/{self.trid}')
        if r.status_code != 200:
            raise RunFailedException(f'Failed to get testrun: {r.status_code}')
        return NewTestRun.parse_raw(r.text)

    def post(self, url, **kwargs):
        r = self.http_client.post(f'testrun/{self.trid}/{url}', **kwargs)
        if r.status_code not in [200, 204]:
            raise RunFailedException(f'Failed to post {url}: {r.status_code}')
        return r


app = App()
