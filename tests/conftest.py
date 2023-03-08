import os
import shutil
from uuid import uuid4

import pytest
from loguru import logger
from pymongo import MongoClient

from common.enums import PlatformEnum
from common.schemas import OrganisationSummary, Project, NewTestRun
from common.settings import settings


@pytest.fixture(autouse=True)
def init():
    settings.MONGO_DATABASE = 'unittest'
    settings.TEST = True
    logger.remove()
    client = MongoClient()
    client.drop_database('unittest')
    yield


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
def testrun(project: Project) -> NewTestRun:
    return NewTestRun(url='git@github.org/dummy.git',
                    id=20,
                    local_id=1,
                    sha='deadbeef0101',
                    project=project,
                    status='started',
                    branch='master')
