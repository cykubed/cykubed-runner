import json
import os
import shutil

from freezegun import freeze_time
from redis import Redis

import builder
from common.enums import AgentEventType
from common.schemas import NewTestRun, AgentEvent
from settings import settings


@freeze_time('2022-04-03 14:10:00Z')
def test_build_no_node_cache(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                             fixturedir):
    msgs = redis.lrange('messages', 0, -1)
    assert not msgs
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.BUILD_DIR, dirs_exist_ok=True)

    builder.build(testrun.id)

    expected_commands = [
        'npm ci',
        'cypress verify',
        'ng build --output-path=dist'
    ]
    assert len(runcmd.call_args_list) == len(expected_commands)
    for i, cmd in enumerate(runcmd.call_args_list):
        assert expected_commands[i] == cmd.args[0]

    msgs = redis.lrange('messages', 0, -1)
    msg_dicts = [json.loads(m) for m in msgs]

    log_msgs = [x['msg']['msg'] for x in msg_dicts if x['type'] == 'log']
    assert log_msgs == ['Build distribution for test run 1', 'Creating node distribution',
                        'Building new node cache using npm',
                        'Created node environment in 0.0s', 'Building app']

    event = AgentEvent.parse_raw(msgs[-1])
    assert event.type == AgentEventType.build_completed
    assert event.testrun_id == 20


@freeze_time('2022-04-03 14:10:00Z')
def test_build_with_node_cache(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                               fixturedir):
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.BUILD_DIR, dirs_exist_ok=True)
    # fake an empty node_modules
    os.makedirs(os.path.join(settings.NODE_CACHE_DIR, 'node_modules'))

    builder.build(testrun.id)

    expected_commands = [
        'ng build --output-path=dist'
    ]
    for i, cmd in enumerate(runcmd.call_args_list):
        assert cmd.args[0] == expected_commands[i]
