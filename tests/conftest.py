import os
import shutil
import tempfile

import pytest
from httpx import Response
from loguru import logger

from cykubedrunner.app import app
from cykubedrunner.common.enums import PlatformEnum
from cykubedrunner.common.schemas import Project, NewTestRun, AgentLogMessage
from cykubedrunner.settings import settings


@pytest.fixture(autouse=True)
def initdb():
    settings.TEST = True
    settings.SCRATCH_DIR = tempfile.mkdtemp()
    settings.BUILD_DIR = os.path.join(settings.SCRATCH_DIR, 'build')
    os.mkdir(settings.BUILD_DIR)
    logger.remove()
    yield
    shutil.rmtree(settings.SCRATCH_DIR)


@pytest.fixture
def fixturedir():
    return os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture()
def project() -> Project:
    return Project(id=10,
                   name='project',
                   repos='project',
                   default_branch='master',
                   agent_id=1,
                   browser='chrome',
                   platform=PlatformEnum.GITHUB,
                   url='git@github.org/dummy.git',
                   docker_image=dict(image='cykubed-runner:1234', browser='chrome',
                                     node_major_version=16),
                   start_runners_first=False,
                   build_cmd='ng build --output-path=dist',
                   organisation_id=5)


@pytest.fixture()
def testrun(mocker, project: Project) -> NewTestRun:
    tr = NewTestRun(url='git@github.org/dummy.git',
                    id=20,
                    local_id=1,
                    sha='deadbeef0101',
                    project=project,
                    status='started',
                    branch='master')
    mocker.patch('cykubedrunner.builder.get_node_version', return_value='v18.17.0')
    app.init_http_client(20)
    return tr


@pytest.fixture()
def fetch_testrun_mock(respx_mock, testrun: NewTestRun):
    return respx_mock.get(f'https://api.cykubed.com/agent/testrun/{testrun.id}').mock(
        return_value=Response(200, content=testrun.json()))


@pytest.fixture()
def build_completed_mock(respx_mock, testrun: NewTestRun):
    return respx_mock.post(f'https://api.cykubed.com/agent/testrun/{testrun.id}/build-completed').mock(
        return_value=Response(200))


@pytest.fixture()
def post_logs_mock(respx_mock, testrun: NewTestRun):
    r = respx_mock.post(f'https://api.cykubed.com/agent/testrun/{testrun.id}/log').mock(
        return_value=Response(200))

    def extract():
        logs = []
        for call in r.calls:
            appmsg = AgentLogMessage.parse_raw(call.request.content.decode())
            logs.append(appmsg.msg.msg)
        return logs

    return extract

