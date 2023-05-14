import os
import shutil

from freezegun import freeze_time
from redis import Redis

import builder
from common.enums import AgentEventType
from common.schemas import NewTestRun, AgentEvent, AgentCloneCompletedEvent
from settings import settings


@freeze_time('2022-04-03 14:10:00Z')
def test_clone(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
               fixturedir):
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.BUILD_DIR, dirs_exist_ok=True)

    builder.clone(testrun.id)

    expected_commands = [
        f'rm -fr {settings.BUILD_DIR}/*',
        # this is to avoid git complaining about the root ownership of the folder (even though the group is correct)
        f'git config --global --add safe.directory {settings.BUILD_DIR}',
        f'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101'
    ]
    for i, cmd in enumerate(runcmd.call_args_list):
        assert expected_commands[i] == cmd.args[0]

    specs = {'cypress/e2e/nonsense/test4.spec.ts',
             'cypress/e2e/nonsense/another-test.spec.ts',
             'cypress/e2e/stuff/test1.spec.ts',
             'cypress/e2e/stuff/test2.spec.ts',
             'cypress/e2e/stuff/test3.spec.ts'}

    redis_events = redis.lrange('messages', 0, -1)
    msgs = [AgentEvent.parse_raw(m) for m in redis_events]
    # last message should be clone_completed
    assert msgs[-1].type == AgentEventType.clone_completed
    clone_completed_event = AgentCloneCompletedEvent.parse_raw(redis_events[-1])

    assert clone_completed_event.cache_key == '74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2'
    assert clone_completed_event.testrun_id == 20
    assert set(clone_completed_event.specs) == specs
