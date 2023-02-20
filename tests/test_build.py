import os

import httpx
import pytest

from build import create_node_environment
from common.schemas import NewTestRun


@pytest.mark.respx
def test_create_node_environment_cache_miss(respx_mock, mocker, testrun, fixturedir):
    mocker.patch('build.logger')
    runcmd = mocker.patch('build.runcmd')
    mocker.patch('os.remove')
    mocker.patch('os.mkdir')
    upload_to_cache = mocker.patch('build.upload_to_cache')
    project = os.path.join(fixturedir, 'project')
    respx_mock.head(
        'http://127.0.0.1:5001/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4').mock(
        return_value=httpx.Response(404))
    tr = NewTestRun.parse_obj(testrun)
    create_node_environment(tr, project)

    cmds = [x[0][0] for x in runcmd.call_args_list]
    assert cmds == ['npm ci',
                    'cypress install',
                    'tar cf /tmp/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4 -I lz4 node_modules cypress_cache']

    upload_to_cache.assert_called_with('/tmp/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4',
                                       '74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4')

    # try again with yarn
    respx_mock.head(
        'http://127.0.0.1:5001/c286ee67fcc0b00334cb1d1fcaa1940fa97a9a641d2396e20f06e7d67166d47b.tar.lz4').mock(
        return_value=httpx.Response(404))
    runcmd = mocker.patch('build.runcmd')
    project = os.path.join(fixturedir, 'project-yarn')
    create_node_environment(tr, project)

    cmds = [x[0][0] for x in runcmd.call_args_list]
    assert cmds[0] == 'yarn install --pure-lockfile'


@pytest.mark.respx
def test_create_node_environment_cache_hit(respx_mock, mocker, testrun, fixturedir):
    mocker.patch('build.logger')
    fetch_from_cache = mocker.patch('build.fetch_from_cache')
    project = os.path.join(fixturedir, 'project')
    respx_mock.head(
        'http://127.0.0.1:5001/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4').mock(
        return_value=httpx.Response(200))
    create_node_environment(NewTestRun.parse_obj(testrun), project)

    fetch_from_cache.assert_called_once()
