import os
import shutil

import tempfile
import pytest
from loguru import logger
from redis.asyncio import Redis as AsyncRedis

from common.enums import PlatformEnum
from common.schemas import OrganisationSummary, Project, NewTestRun
from redis import Redis

from common.settings import settings


@pytest.fixture()
def redis(mocker):
    r = Redis(host=settings.REDIS_HOST, db=1, decode_responses=True)
    r.flushdb()
    mocker.patch('utils.async_redis', return_value=AsyncRedis(host=settings.REDIS_HOST,
                                                              db=1, decode_responses=True))
    return r


@pytest.fixture(autouse=True)
async def initdb(redis):
    settings.TEST = True
    settings.REDIS_DB = 1
    settings.SCRATCH_DIR = tempfile.mkdtemp()
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
