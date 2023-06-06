import json
import os
import shutil

from freezegun import freeze_time
from redis import Redis

import builder
from common.enums import AgentEventType
from common.schemas import NewTestRun, AgentEvent, AgentBuildCompletedEvent
from settings import settings


@freeze_time('2022-04-03 14:10:00Z')
def test_build_no_node_cache(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                             fixturedir):
    msgs = redis.lrange('messages', 0, -1)
    assert not msgs
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.src_dir, dirs_exist_ok=True)

    builder.build(testrun.id)

    expected_commands = [
        'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101',
        'npm ci',
        'cypress verify',
        'ng build --output-path=dist'
    ]
    commands = [x.args[0] for x in runcmd.call_args_list]
    assert expected_commands == commands

    msgs = redis.lrange('messages', 0, -1)
    msg_dicts = [json.loads(m) for m in msgs]

    log_msgs = [x['msg']['msg'] for x in msg_dicts if x['type'] == 'log']
    assert log_msgs == ['Cloning repository',
                        'Cloned branch master',
                        'Build distribution for test run 1',
                        'Creating node distribution',
                        'Building new node cache using npm',
                        'Created node environment in 0.0s',
                        'Building app']

    event = AgentBuildCompletedEvent.parse_raw(msgs[-1])
    assert event.type == AgentEventType.build_completed
    assert event.testrun_id == 20
    assert set(event.specs) == {'cypress/e2e/nonsense/test4.spec.ts',
                                'cypress/e2e/nonsense/another-test.spec.ts',
                                'cypress/e2e/stuff/test1.spec.ts',
                                'cypress/e2e/stuff/test2.spec.ts',
                                'cypress/e2e/stuff/test3.spec.ts'}


@freeze_time('2022-04-03 14:10:00Z')
def test_build_with_node_cache(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                               fixturedir):
    runcmd = mocker.patch('builder.runcmd')
    shutil.copytree(os.path.join(fixturedir, 'project'), settings.src_dir, dirs_exist_ok=True)
    # fake an empty node_modules
    os.makedirs(os.path.join(settings.BUILD_DIR, 'node_modules'))

    builder.build(testrun.id)

    expected_commands = [
        'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101',
        f'mv {settings.BUILD_DIR}/node_modules {settings.src_dir}',
        'ng build --output-path=dist'
    ]
    commands = [x.args[0] for x in runcmd.call_args_list]
    assert commands == expected_commands
