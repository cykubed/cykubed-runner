import os
import shutil

from httpx import Response

from cykubedrunner.common.schemas import NewTestRun, AgentSpecCompleted
from cykubedrunner.runner import run
from cykubedrunner.settings import settings


def test_cypress_run(respx_mock,
                     mocker,
                     cypress_fixturedir,
                     json_fixture_fetcher,
                     testrun: NewTestRun,
                     json_formatter,
                     mock_uploader,
                     multipart_parser,
                     post_logs_mock
                     ):
    settings.TEST = True
    testrun.project.browsers = ['electron', 'firefox']
    os.makedirs(os.path.join(settings.src_dir, 'node_modules'))
    os.makedirs(os.path.join(settings.BUILD_DIR, 'cypress_cache'))

    respx_mock.get(f'https://api.cykubed.com/agent/testrun/{testrun.id}').mock(
        return_value=Response(200, content=testrun.json()))

    next_spec_mock = respx_mock.post('https://api.cykubed.com/agent/testrun/20/next-spec').mock(side_effect=[
        Response(status_code=200, content='nonsense/test4.spec.ts'),
        Response(status_code=200, content='stuff/test1.spec.ts'),
        Response(status_code=204)
    ])
    mocker.patch('cykubedrunner.runner.start_server', return_value=mocker.Mock())

    spec_completed_mock = respx_mock.post('https://api.cykubed.com/agent/testrun/20/spec-completed').mock(
        side_effect=[Response(status_code=200),
                     Response(status_code=200)
                     ])

    upload_mock = mock_uploader(5)

    def create_process_side_effects(runner):
        # copy results from fixture dir
        filename = runner.file.split('/')[1].split('.')[0]
        srcdir = os.path.join(cypress_fixturedir, 'full-run', runner.browser, filename)
        shutil.copytree(srcdir, runner.screenshots_folder, dirs_exist_ok=True)
        shutil.copy(os.path.join(srcdir, 'out.json'), runner.results_file)
        return mocker.Mock(returncode=0)

    # autospec to ensure we get the self i.e the runner object
    mocker.patch('cykubedrunner.baserunner.BaseSpecRunner.create_process',
                 side_effect=create_process_side_effects, autospec=True)

    run(20)

    # we asked for 3 specs - we got 2 and a 204
    assert next_spec_mock.call_count == 3

    # 2 completed specs
    assert spec_completed_mock.call_count == 2

    # confirm the posted spec completions
    spec_completed1 = AgentSpecCompleted.parse_raw(spec_completed_mock.calls[0].request.content.decode())
    assert spec_completed1.file == 'nonsense/test4.spec.ts'
    assert spec_completed1.finished
    # print(spec_completed1.result.json(indent=4))
    assert spec_completed1.result.json(indent=4) == json_fixture_fetcher('cypress/full-run/expected/test4.json')

    spec_completed2 = AgentSpecCompleted.parse_raw(spec_completed_mock.calls[1].request.content.decode())
    assert spec_completed2.file == 'stuff/test1.spec.ts'
    assert spec_completed2.finished
    # print(spec_completed2.result.json(indent=4))
    assert spec_completed2.result.json(indent=4) == json_fixture_fetcher('cypress/full-run/expected/test1.json')

    # 5 image uploads in a single upload POST
    assert upload_mock.call_count == 1
    assert len(multipart_parser(upload_mock.calls[0].request)) == 5
