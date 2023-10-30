import os

from cykubedrunner.settings import settings


class App(object):
    def __init__(self):
        self.is_spot = False
        self.is_yarn = os.path.exists(os.path.join(settings.src_dir, 'yarn.lock'))
        self.is_yarn_modern = False
        self.is_yarn_zero_install = False
        self.is_terminating = False
        self.specs_completed = set()

        with open('/etc/hostname') as f:
            self.hostname = f.read().strip()


app = App()
