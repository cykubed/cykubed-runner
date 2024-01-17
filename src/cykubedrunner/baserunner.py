import os
import shutil
import subprocess
from abc import ABC, abstractmethod

from cykubedrunner.app import app
from cykubedrunner.common import schemas
from cykubedrunner.common.exceptions import RunFailedException
from cykubedrunner.common.schemas import NewTestRun, AgentSpecCompleted, SpecTests
from cykubedrunner.common.utils import utcnow
from cykubedrunner.server import ServerThread
from cykubedrunner.settings import settings
from cykubedrunner.utils import logger


class BaseSpecRunner(ABC):
    def __init__(self, server: ServerThread, testrun: NewTestRun, file: str):
        self.server = server
        self.testrun = testrun
        self.file = file
        self.results_dir = settings.get_results_dir()
        self.results_file = os.path.join(self.results_dir, 'out.json')
        if os.path.exists(self.results_dir):
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)
        self.started = None
        if self.server:
            self.base_url = f'http://localhost:{self.server.port}'
        else:
            self.base_url = f'http://localhost:{self.testrun.project.server_port}'

    @abstractmethod
    def get_args(self):
        pass

    @abstractmethod
    def parse_results(self) -> schemas.SpecTests:
        pass

    def get_env(self):
        return dict()

    def create_process(self) -> subprocess.CompletedProcess:
        args = self.get_args()
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

    def run(self) -> SpecTests:
        self.started = utcnow()
        logger.debug(f'Run tests for {self.file}')
        try:
            proc = self.create_process()
            if not os.path.exists(self.results_file):
                if proc.returncode == 1:
                    # there was a problem with the run - log output
                    logger.error(f"Cypress run failed to produce any results:\n {proc.stdout}\n{proc.stderr}")
                raise RunFailedException(f'Missing results file')

            # parse the results
            return self.parse_results()
        except subprocess.TimeoutExpired:
            logger.info(f'Exceeded deadline for spec {self.file}')

            r = app.http_client.post('/spec-completed',
                                     content=AgentSpecCompleted(
                                         result=SpecTests(timeout=True, tests=[]),
                                         file=self.file,
                                         finished=utcnow()).json())
            if r.status_code != 200:
                raise RunFailedException(f'Failed to set spec completed: {r.status_code}: {r.text}')
