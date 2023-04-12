# import os
#
# import httpx
# import pytest
#
# from build import create_node_environment, clone_and_build
# from common.schemas import NewTestRun
# from common.settings import settings
#
#
# @pytest.mark.respx
# def test_create_node_environment_cache_miss(respx_mock, mocker, testrun, fixturedir):
#     mocker.patch('build.logger')
#     runcmd = mocker.patch('build.runcmd')
#     mocker.patch('os.remove')
#     mocker.patch('os.mkdir')
#     settings.get_build_dir() = os.path.join(fixturedir, 'project')
#     respx_mock.head(
#         'http://127.0.0.1:5001/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4').mock(
#         return_value=httpx.Response(404))
#     tr = NewTestRun.parse_obj(testrun)
#     create_node_environment(tr)
#
#     cmds = [x[0][0] for x in runcmd.call_args_list]
#     assert cmds == ['npm ci',
#                     'cypress install']
#
#     # try again with yarn
#     respx_mock.head(
#         'http://127.0.0.1:5001/c286ee67fcc0b00334cb1d1fcaa1940fa97a9a641d2396e20f06e7d67166d47b.tar.lz4').mock(
#         return_value=httpx.Response(404))
#     runcmd = mocker.patch('build.runcmd')
#     settings.get_build_dir() = os.path.join(fixturedir, 'project-yarn')
#     create_node_environment(tr)
#
#     cmds = [x[0][0] for x in runcmd.call_args_list]
#     assert cmds[0] == 'yarn install'
#
#
# @pytest.mark.respx
# def test_create_node_environment_cache_hit(respx_mock, mocker, testrun, fixturedir):
#     mocker.patch('build.logger')
#     fetch_from_cache = mocker.patch('build.fetch_from_cache')
#     settings.get_build_dir() = os.path.join(fixturedir, 'project')
#     respx_mock.head(
#         'http://127.0.0.1:5001/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4').mock(
#         return_value=httpx.Response(200))
#     create_node_environment(NewTestRun.parse_obj(testrun))
#
#     fetch_from_cache.assert_called_once()
#
#
# def test_clone_and_build(mocker, testrun: NewTestRun, fixturedir):
#     testrun.sha = 'deadbeef0101'
#     trdict = testrun.dict()
#     runs_coll().insert_one(trdict)
#
#     mocker.patch('build.logger')
#     mocker.patch('build.clone_repos')
#     settings.get_build_dir() = fixturedir+'/project'
#     mocker.patch('build.create_node_environment',
#                  return_value=('74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2', True))
#
#     runcmd = mocker.patch('build.runcmd')
#     # create some dummy files
#     with open('/tmp/deadbeef0101.tar.lz4', 'wb') as f:
#         f.write('dummy'.encode())
#     with open('/tmp/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4', 'wb') as f:
#         f.write('dummy'.encode())
#
#     clone_and_build(20)
#
#     # this will have built and stored the node cache and app distribution in GridFS
#     tr = runs_coll().find_one({'id': 20})
#     assert tr['status'] == 'running'
#
#     assert check_file_exists('deadbeef0101')
#     assert check_file_exists('74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2')
#
#     specs = {x['file'] for x in specs_coll().find({'trid': 20})}
#     assert specs == {'cypress/e2e/stuff/test2.spec.ts',
#                      'cypress/e2e/stuff/test3.spec.ts',
#                      'cypress/e2e/stuff/test1.spec.ts',
#                      'cypress/e2e/nonsense/test4.spec.ts',
#                      'cypress/e2e/nonsense/another-test.spec.ts'}
#
#     cmds = [x[0][0] for x in runcmd.call_args_list]
#     assert cmds == [
#         'ng build --output-path=dist',
#         'tar cf /tmp/deadbeef0101.tar.lz4 --exclude="node_modules" --exclude="cypress_cache" --exclude=".git" . -I '
#         'lz4',
#         'tar cf /tmp/74be0866a9e180f69bc38c737d112e4b744211c55a4028e8ccb45600118c0cd2.tar.lz4 -I lz4 '
#         'node_modules cypress_cache']
