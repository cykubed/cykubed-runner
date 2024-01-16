import os
import shutil
import subprocess
from abc import ABC, abstractmethod

from cykubedrunner.common.schemas import NewTestRun
from cykubedrunner.server import ServerThread
from cykubedrunner.settings import settings
from cykubedrunner.utils import logger


class BaseSpecRunner(ABC):
    def __init__(self, server: ServerThread, testrun: NewTestRun, file: str):
        self.server = server
        self.testrun = testrun
        self.file = file
        self.results_dir = settings.get_results_dir()
        self.results_file = f'{self.results_dir}/out.json'
        if os.path.exists(self.results_dir):
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)
        self.started = None

    @abstractmethod
    def get_env(self):
        pass

    def create_process(self, browser=None) -> subprocess.CompletedProcess:
        args = self.get_args(browser)
        fullcmd = ' '.join(args)
        logger.debug(f'Calling runner with args: "{fullcmd}"')

        result = subprocess.run(args,
                                timeout=self.testrun.project.spec_deadline or None,
                                capture_output=True,
                                text=True,
                                env=self.get_env(),
                                cwd=settings.src_dir)
        logger.debug(f'runner stdout: \n{result.stdout}')
        logger.debug(f'runner stderr: \n{result.stderr}')
        return result
