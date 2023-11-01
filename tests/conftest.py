import os
import shutil
import tempfile

import pytest
from loguru import logger
from redis import Redis

from cykubedrunner.common.enums import PlatformEnum
from cykubedrunner.common.schemas import Project, NewTestRun
from cykubedrunner.settings import settings


@pytest.fixture()
def redis(mocker):
    os.environ['REDIS_DB'] = '1'
    r = Redis(db=1, decode_responses=True)
    r.flushdb()
    mocker.patch('cykubedrunner.common.redisutils.get_redis', return_value=r)
    return r


@pytest.fixture(autouse=True)
def initdb(redis):
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
def testrun(project: Project, redis: Redis) -> NewTestRun:
    tr = NewTestRun(url='git@github.org/dummy.git',
                    id=20,
                    local_id=1,
                    sha='deadbeef0101',
                    project=project,
                    status='started',
                    branch='master')
    redis.set(f'testrun:{tr.id}', tr.json())
    return tr
