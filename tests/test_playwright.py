import os
import shutil

from httpx import Response

from cykubedrunner.builder import get_playwright_specs
from cykubedrunner.common.enums import TestFramework
from cykubedrunner.common.schemas import NewTestRun, AgentSpecCompleted
from cykubedrunner.playwright import PlaywrightSpecRunner
from cykubedrunner.runner import run
from cykubedrunner.settings import settings


def test_get_specs(playwright_fixturedir):
    specs = set(get_playwright_specs(os.path.join(playwright_fixturedir, 'project')))
    assert specs == {'tests/another.spec.ts',
                     'tests/example.spec.ts'}


def test_playwright_parse_with_failures(testrun, playwright_fixturedir,
                                        json_fixture_fetcher):
    specrunner = PlaywrightSpecRunner(None, testrun, 'another.spec.ts')
    jsonfile = os.path.join(playwright_fixturedir, 'fails-skips-flakes.json')
    specrunner.results_file = jsonfile
    results = specrunner.parse_results()

    expected = json_fixture_fetcher('playwright/expected-results-fail.json')
    # print(results.json(indent=4))
    assert expected == results.json(indent=4)


def test_playwright_run(respx_mock,
                        mocker,
                        playwright_fixturedir,
                        json_fixture_fetcher,
                        testrun: NewTestRun,
                        json_formatter,
                        post_logs_mock,
                        mock_uploader,
                        multipart_parser,
                        ):
    settings.TEST = True
    testrun.project.browsers = ['chrome']
    testrun.project.test_framework = TestFramework.playwright

    fetch_testrun_mock = respx_mock.get(f'https://api.cykubed.com/agent/testrun/{testrun.id}').mock(
        return_value=Response(200, content=testrun.json()))

    next_spec_mock = respx_mock.post('https://api.cykubed.com/agent/testrun/20/next-spec').mock(side_effect=[
        Response(status_code=200, content='example.spec.ts'),
        Response(status_code=200, content='another.spec.ts'),
        Response(status_code=204)
    ])
    mocker.patch('cykubedrunner.runner.start_server', return_value=mocker.Mock())
    os.makedirs(os.path.join(settings.src_dir, 'node_modules'))

    spec_completed_mock = respx_mock.post('https://api.cykubed.com/agent/testrun/20/spec-completed').mock(
        side_effect=[Response(status_code=200),
                     Response(status_code=200)
                     ])

    upload_mock = mock_uploader(5)

    def create_process_side_effects(runner):
        # copy results from fixture dir
        filename = runner.file.split('.')[0]
        srcdir = os.path.join(playwright_fixturedir, filename)
        shutil.copytree(srcdir, runner.results_dir, dirs_exist_ok=True)
        # rename the paths
        with open(os.path.join(srcdir, 'out.json')) as f:
            result = f.read().replace(f'/{filename}/', f'{runner.results_dir}/')
        with open(os.path.join(runner.results_dir, 'out.json'), 'w') as f:
            f.write(result)

        return mocker.Mock(returncode=0)

    # autospec to ensure we get the self i.e the runner object
    mocker.patch('cykubedrunner.baserunner.BaseSpecRunner.create_process',
                 side_effect=create_process_side_effects, autospec=True)

    run()

    assert fetch_testrun_mock.call_count == 1

    # we asked for 3 specs - we got 2 and a 204
    assert next_spec_mock.call_count == 3

    # 2 completed specs
    assert spec_completed_mock.call_count == 2

    # confirm the posted spec completions
    spec_completed1 = AgentSpecCompleted.parse_raw(spec_completed_mock.calls[0].request.content.decode())
    assert spec_completed1.file == 'example.spec.ts'
    assert spec_completed1.finished
    assert spec_completed1.result.json(indent=4) == json_fixture_fetcher('playwright/example/expected-result.json')

    spec_completed2 = AgentSpecCompleted.parse_raw(spec_completed_mock.calls[1].request.content.decode())
    assert spec_completed2.file == 'another.spec.ts'
    assert spec_completed2.finished
    assert spec_completed2.result.json(indent=4) == json_fixture_fetcher('playwright/another/expected-result.json')

    # 5 image uploads in a single upload POST
    assert upload_mock.call_count == 1
    assert len(multipart_parser(upload_mock.calls[0].request)) == 5
