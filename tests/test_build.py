import json
import os
import shutil

from freezegun import freeze_time
from redis import Redis

import builder
from common.enums import AgentEventType
from common.schemas import AgentTestRun, AgentEvent
from settings import settings


@freeze_time('2022-04-03 14:10:00Z')
def test_build_no_node_cache(mocker, respx_mock, cloned_testrun: AgentTestRun, redis: Redis,
                             fixturedir):
    msgs = redis.lrange('messages', 0, -1)
    assert not msgs
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.BUILD_DIR)

    builder.build(cloned_testrun.id)

    expected_commands = [
        'npm ci',
        'cypress install',
        'ng build --output-path=dist'
    ]
    for i, cmd in enumerate(runcmd.call_args_list):
        assert expected_commands[i] == cmd.args[0]

    msgs = redis.lrange('messages', 0, -1)
    # first 6 messages are log messages
    assert len(msgs) == 7
    msg_dicts = [json.loads(m) for m in msgs]

    log_msgs = [x['msg']['msg'] for x in msg_dicts if x['type'] == 'log']
    assert log_msgs == ['Build distribution for test run 1', 'Creating node distribution',
                        'Building new node cache using npm', 'Installing Cypress binary',
                        'Created node environment in 0.0s', 'Building app']

    event = AgentEvent.parse_raw(msgs[6])
    assert event.type == AgentEventType.build_completed
    assert event.testrun_id == 20


@freeze_time('2022-04-03 14:10:00Z')
def test_build_with_node_cache(mocker, respx_mock, cloned_testrun: AgentTestRun, redis: Redis,
                              fixturedir):
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.BUILD_DIR)
    # fake an empty node_modules
    os.makedirs(os.path.join(settings.NODE_CACHE_DIR, 'node_modules'))

    builder.build(cloned_testrun.id)

    expected_commands = [
        'ng build --output-path=dist'
    ]
    for i, cmd in enumerate(runcmd.call_args_list):
        assert expected_commands[i] == cmd.args[0]
