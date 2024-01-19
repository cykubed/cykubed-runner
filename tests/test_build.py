import os
import shutil

from freezegun import freeze_time

from cykubedrunner import builder
from cykubedrunner.common.schemas import NewTestRun, AgentBuildCompleted
from cykubedrunner.settings import settings


@freeze_time('2022-04-03 14:10:00Z')
def test_build_no_node_cache(mocker,
                             fetch_testrun_mock,
                             build_completed_mock,
                             post_logs_mock,
                             testrun: NewTestRun,
                             cypress_fixturedir):
    runcmd = mocker.patch('cykubedrunner.builder.runcmd')
    shutil.copytree(os.path.join(cypress_fixturedir, 'project'), settings.src_dir, dirs_exist_ok=True)

    builder.build()

    assert fetch_testrun_mock.called

    expected_commands = [
        'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101',
        'npm ci',
        'cypress verify',
        'ng build --output-path=dist'
    ]
    commands = [x.args[0] for x in runcmd.call_args_list]
    assert expected_commands == commands

    log_msgs = post_logs_mock()

    assert log_msgs == ['Cloning repository',
                        'Cloned branch master',
                        'Build distribution for test run 1',
                        'Using node v18.17.0',
                        'Creating node distribution',
                        'Building new node cache using npm',
                        'Created node environment in 0.0s',
                        'Building app']

    assert build_completed_mock.called
    event = AgentBuildCompleted.parse_raw(build_completed_mock.calls.last.request.content.decode())
    assert set(event.specs) == {'cypress/e2e/nonsense/test4.spec.ts',
                                'cypress/e2e/nonsense/another-test.spec.ts',
                                'cypress/e2e/stuff/test1.spec.ts',
                                'cypress/e2e/stuff/test2.spec.ts',
                                'cypress/e2e/stuff/test3.spec.ts'}


@freeze_time('2022-04-03 14:10:00Z')
def test_build_with_node_cache(mocker,
                               fetch_testrun_mock,
                               build_completed_mock,
                               post_logs_mock,
                               testrun: NewTestRun,
                               cypress_fixturedir):
    runcmd = mocker.patch('cykubedrunner.builder.runcmd')
    shutil.copytree(os.path.join(cypress_fixturedir, 'project'), settings.src_dir, dirs_exist_ok=True)
    # fake an empty node_modules
    os.makedirs(os.path.join(settings.BUILD_DIR, 'node_modules'))

    builder.build()

    expected_commands = [
        'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101',
        f'mv {settings.BUILD_DIR}/node_modules {settings.src_dir}',
        'ng build --output-path=dist'
    ]
    commands = [x.args[0] for x in runcmd.call_args_list]
    assert commands == expected_commands


def test_build_yarn1_no_cache(mocker, fetch_testrun_mock,
                               build_completed_mock,
                               post_logs_mock, testrun: NewTestRun,
                               cypress_fixturedir):
    runcmd = mocker.patch('cykubedrunner.builder.runcmd')
    shutil.copytree(os.path.join(cypress_fixturedir, 'project-yarn'), settings.src_dir, dirs_exist_ok=True)

    builder.build()

    expected_commands = [
        'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101',
        f'yarn install --pure-lockfile --cache-folder={settings.BUILD_DIR}/.yarn-cache',
        'cypress verify',
        'ng build --output-path=dist'
    ]
    commands = [x.args[0] for x in runcmd.call_args_list]
    print(commands)
    assert commands == expected_commands


def test_build_yarn2_no_cache(mocker, fetch_testrun_mock,
                               build_completed_mock,
                               post_logs_mock, testrun: NewTestRun,
                               cypress_fixturedir):
    runcmd = mocker.patch('cykubedrunner.builder.runcmd')
    shutil.copytree(os.path.join(cypress_fixturedir, 'project-yarn2'), settings.src_dir, dirs_exist_ok=True)

    builder.build()

    expected_commands = [
        'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101',
        'yarn set version berry',
        'yarn install',
        'cypress verify',
        'ng build --output-path=dist'
    ]
    commands = [x.args[0] for x in runcmd.call_args_list]
    assert commands == expected_commands


def test_build_yarn2_with_cache(mocker, fetch_testrun_mock,
                               build_completed_mock,
                               post_logs_mock, testrun: NewTestRun,
                               cypress_fixturedir):
    runcmd = mocker.patch('cykubedrunner.builder.runcmd')
    shutil.copytree(os.path.join(cypress_fixturedir, 'project-yarn2'), settings.src_dir, dirs_exist_ok=True)
    os.mkdir(settings.yarn2_global_cache)

    builder.build()

    expected_commands = [
        'git clone --recursive git@github.org/dummy.git .',
        'git reset --hard deadbeef0101',
        'yarn set version berry',
        'yarn install',
        'ng build --output-path=dist'
    ]
    commands = [x.args[0] for x in runcmd.call_args_list]
    assert commands == expected_commands
