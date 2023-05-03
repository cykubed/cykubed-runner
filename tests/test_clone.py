import os
import shutil

from freezegun import freeze_time
from redis import Redis

import builder
from common.schemas import NewTestRun, AgentEvent
from settings import settings


@freeze_time('2022-04-03 14:10:00Z')
def test_clone(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
               fixturedir):
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.dist_dir, dirs_exist_ok=True)

    builder.clone(testrun.id)

    expected_commands = [
        f'rm -fr {settings.dist_dir}',
        # this is to avoid git complaining about the root ownership of the folder (even though the group is correct)
        f'git config --global --add safe.directory {settings.BUILD_DIR}',
        f'git clone --recursive git@github.org/dummy.git {settings.dist_dir}',
        'git reset --hard deadbeef0101'
    ]
    for i, cmd in enumerate(runcmd.call_args_list):
        assert expected_commands[i] == cmd.args[0]

    specs = {'cypress/e2e/nonsense/test4.spec.ts',
             'cypress/e2e/nonsense/another-test.spec.ts',
             'cypress/e2e/stuff/test1.spec.ts',
             'cypress/e2e/stuff/test2.spec.ts',
             'cypress/e2e/stuff/test3.spec.ts'}
    assert redis.smembers('testrun:20:specs') == specs

    assert redis.llen('messages') == 4

    msg = AgentEvent.parse_raw(redis.lrange('messages', 0, -1)[-1])
    assert msg.testrun_id == 20
    assert msg.duration is not None
