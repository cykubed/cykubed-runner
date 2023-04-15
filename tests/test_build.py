import os
import re
import shutil

import httpx
import respx
from redis import Redis

from build import clone_and_build
from common.schemas import NewTestRun
from common.settings import settings


@respx.mock
async def test_clone_and_build_no_node_env(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                                            fixturedir):

    mock_fsclient = mocker.AsyncMock()
    mock_fsclient.exists = mocker.AsyncMock(return_value=False)
    mock_fsclient.upload = mocker.AsyncMock()
    mocker.patch('build.shutil.rmtree')

    httpclient = httpx.AsyncClient(base_url='https://dummy.cykubed.com/agent/testrun/20')
    status_route = respx_mock.post('https://dummy.cykubed.com/agent/testrun/20/status/building')
    runcmd = mocker.patch('build.runcmd')

    shutil.copytree(os.path.join(fixturedir, 'project'), settings.get_build_dir())
    await clone_and_build(testrun.id, mock_fsclient, httpclient)

    assert status_route.called

    expected_commands = [
        r'git clone --recursive git@github.org/dummy.git /tmp/(.+)/build',
        'git reset --hard deadbeef0101',
        'npm ci',
        'cypress install',
        'ng build --output-path=dist',
        f'tar cf {settings.SCRATCH_DIR}/tmp/deadbeef0101.tar.lz4 --exclude="node_modules" --exclude="cypress_cache" --exclude=".git" . -I lz4',
        f'tar cf {settings.SCRATCH_DIR}/tmp/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4'
                    ' -I lz4 node_modules cypress_cache'
    ]
    for i, cmd in enumerate(runcmd.call_args_list):
        assert re.match(expected_commands[i], cmd.args[0]) is not None

    mock_fsclient.exists.assert_called()
    mock_fsclient.upload.assert_called()
    assert len(mock_fsclient.upload.call_args_list) == 2
    args = {x.args[0] for x in mock_fsclient.upload.call_args_list}
    assert args == {f'{settings.SCRATCH_DIR}/tmp/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4',
                    f'{settings.SCRATCH_DIR}/tmp/deadbeef0101.tar.lz4'}


@respx.mock
async def test_clone_and_build_node_cache_hit(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                                            fixturedir):

    mock_fsclient = mocker.AsyncMock()

    def exists_fn(x):
        return x == '74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4'

    mock_fsclient.exists = mocker.AsyncMock(side_effect=exists_fn)
    mock_fsclient.upload = mocker.AsyncMock()
    mocker.patch('build.shutil.rmtree')

    httpclient = httpx.AsyncClient(base_url='https://dummy.cykubed.com/agent/testrun/20')
    status_route = respx_mock.post('https://dummy.cykubed.com/agent/testrun/20/status/building')
    runcmd = mocker.patch('build.runcmd')

    shutil.copytree(os.path.join(fixturedir, 'project'), settings.get_build_dir())
    await clone_and_build(testrun.id, mock_fsclient, httpclient)

    assert status_route.called

    expected_commands = [
        r'git clone --recursive git@github.org/dummy.git /tmp/(.+)/build',
        'git reset --hard deadbeef0101',
        'ng build --output-path=dist',
        f'tar cf {settings.SCRATCH_DIR}/tmp/deadbeef0101.tar.lz4 --exclude="node_modules" --exclude="cypress_cache" --exclude=".git" . -I lz4',
    ]

    for i, cmd in enumerate(runcmd.call_args_list):
        assert re.match(expected_commands[i], cmd.args[0]) is not None

    mock_fsclient.exists.assert_called()
    mock_fsclient.upload.assert_called_once()
    args = {x.args[0] for x in mock_fsclient.upload.call_args_list}
    assert args == {f'{settings.SCRATCH_DIR}/tmp/deadbeef0101.tar.lz4'}


@respx.mock
async def test_clone_and_build_all_cache_hits(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                                              fixturedir):

    mock_fsclient = mocker.AsyncMock()
    mock_fsclient.exists = mocker.AsyncMock(return_value=True)
    mock_fsclient.upload = mocker.AsyncMock()
    mocker.patch('build.shutil.rmtree')

    httpclient = httpx.AsyncClient(base_url='https://dummy.cykubed.com/agent/testrun/20')
    status_route = respx_mock.post('https://dummy.cykubed.com/agent/testrun/20/status/building')
    runcmd = mocker.patch('build.runcmd')

    shutil.copytree(os.path.join(fixturedir, 'project'), settings.get_build_dir())
    await clone_and_build(testrun.id, mock_fsclient, httpclient)

    assert status_route.called

    expected_commands = [
        r'git clone --recursive git@github.org/dummy.git /tmp/(.+)/build',
        'git reset --hard deadbeef0101'
     ]

    for i, cmd in enumerate(runcmd.call_args_list):
        assert re.match(expected_commands[i], cmd.args[0]) is not None

    mock_fsclient.exists.assert_called()
    mock_fsclient.upload.assert_not_called()

