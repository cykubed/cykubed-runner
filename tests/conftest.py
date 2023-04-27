import os
import shutil
import tempfile

import pytest
from loguru import logger
from redis import Redis

from common.enums import PlatformEnum
from common.schemas import OrganisationSummary, Project, NewTestRun, AgentTestRun
from settings import settings


@pytest.fixture()
def redis(mocker):
    r = Redis(db=1, decode_responses=True)
    r.flushdb()
    mocker.patch('builder.sync_redis', return_value=r)
    mocker.patch('cypress.sync_redis', return_value=r)
    mocker.patch('utils.sync_redis', return_value=r)
    return r


@pytest.fixture(autouse=True)
def initdb(redis):
    settings.TEST = True
    settings.SCRATCH_DIR = tempfile.mkdtemp()
    settings.BUILD_DIR = os.path.join(settings.SCRATCH_DIR, 'build')
    settings.NODE_CACHE_DIR = os.path.join(settings.SCRATCH_DIR, 'node')
    logger.remove()
    yield
    shutil.rmtree(settings.SCRATCH_DIR)


@pytest.fixture
def fixturedir():
    return os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture()
def project() -> Project:
    org = OrganisationSummary(id=5, name='MyOrg')
    return Project(id=10,
                   name='project',
                   default_branch='master',
                   agent_id=1,
                   platform=PlatformEnum.GITHUB,
                   url='git@github.org/dummy.git',
                   start_runners_first=False,
                   organisation=org)


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


@pytest.fixture()
def cloned_testrun(redis, testrun: NewTestRun) -> AgentTestRun:
    specs = {'cypress/e2e/nonsense/test4.spec.ts',
             'cypress/e2e/nonsense/another-test.spec.ts',
             'cypress/e2e/stuff/test1.spec.ts',
             'cypress/e2e/stuff/test2.spec.ts',
             'cypress/e2e/stuff/test3.spec.ts'}
    testrun.status = 'building'
    atr = AgentTestRun(specs=specs, cache_key='74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2',
                       **testrun.dict())
    redis.set(f'testrun:{atr.id}', atr.json())
    return atr
