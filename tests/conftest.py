import os

import pytest

from common.enums import PlatformEnum
from common.schemas import OrganisationSummary, Project, NewTestRun


@pytest.fixture
def fixturedir():
    return os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture()
async def project() -> Project:
    org = OrganisationSummary(id=5, name='MyOrg')
    return Project(id=10,
                   name='project',
                   default_branch='master',
                   platform=PlatformEnum.GITHUB,
                   url='git@github.org/dummy.git',
                   organisation=org)


@pytest.fixture()
async def testrun(project: Project) -> NewTestRun:
    return NewTestRun(url='git@github.org/dummy.git',
                    id=10,
                    local_id=1,
                    project=project,
                    status='started',
                    branch='master')
