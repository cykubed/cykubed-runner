import os

import httpx

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

        with open('/etc/hostname') as f:
            self.hostname = f.read().strip()

    def init_http_client(self, trid):
        transport = httpx.HTTPTransport(retries=settings.MAX_HTTP_RETRIES)
        self.http_client = httpx.Client(transport=transport,
                                   base_url=settings.MAIN_API_URL + f'/agent/testrun/{trid}',
                                   headers={'Authorization': f'Bearer {settings.API_TOKEN}'})


app = App()
