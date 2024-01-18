import json
import os
import shutil
import tempfile
from io import BytesIO

import multipart
import pytest
from httpx import Response
from loguru import logger

from cykubedrunner.app import app
from cykubedrunner.common.enums import PlatformEnum
from cykubedrunner.common.schemas import Project, NewTestRun, AgentLogMessage, TestRunBuildState
from cykubedrunner.settings import settings


@pytest.fixture(autouse=True)
def initdb():
    settings.TEST = True
    settings.BUILD_DIR = tempfile.mkdtemp()
    logger.remove()
    yield
    shutil.rmtree(settings.BUILD_DIR)


@pytest.fixture
def fixturedir():
    return os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def cypress_fixturedir(fixturedir):
    return os.path.join(fixturedir, 'cypress')


@pytest.fixture
def playwright_fixturedir(fixturedir):
    return os.path.join(fixturedir, 'playwright')


@pytest.fixture
def fixture_fetcher(fixturedir):
    def fetch(name):
        with open(os.path.join(fixturedir, name)) as f:
            return f.read()
    return fetch


@pytest.fixture
def json_formatter():
    def fmt(src):
        return json.dumps(json.loads(src), indent=4)
    return fmt


@pytest.fixture
def json_fixture_fetcher(fixture_fetcher, json_formatter):
    def fetch(name):
        return json_formatter(fixture_fetcher(name))
    return fetch


@pytest.fixture
def multipart_parser():
    def parse(request):
        uploaded_content = request.content
        boundary = request.headers['Content-Type'].split(';')[1].split('=')[1]
        return list(multipart.MultipartParser(BytesIO(uploaded_content), boundary))
    return parse


@pytest.fixture()
def mock_uploader(respx_mock, testrun):
    def upload(count: int):
        return respx_mock.post(f'https://api.cykubed.com/agent/testrun/{testrun.id}/upload-artifacts').mock(
            return_value=Response(200, json=
            {'urls': [f'https://api.cykubed.com/artifacts/image{i}.png' for i in range(0, count)]}))
    return upload


@pytest.fixture()
def project() -> Project:
    return Project(id=10,
                   name='project',
                   repos='project',
                   default_branch='master',
                   agent_id=1,
                   browser='chrome',
                   app_framework='angular',
                   test_framework='cypress',
                   server_port=4200,
                   url='git@github.org/dummy.git',
                   platform=PlatformEnum.GITHUB,
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
                    image='us-docker.pkg.dev/cykubed/public/runner/cypress-node-20:1.0.0',
                    status='started',
                    branch='master',
                    buildstate=TestRunBuildState(testrun_id=20))
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

