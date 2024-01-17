import json
import os
from unittest import skip

from freezegun import freeze_time
from httpx import Response

from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.schemas import NewTestRun, SpecTests, TestResult, SpecTest
from cykubedrunner.runner import run
from cykubedrunner.settings import settings


@skip('Going to properly refactor this')
@freeze_time('2022-04-03 14:10:00Z')
def test_cypress(mocker, respx_mock,
                 fetch_testrun_mock,
                 testrun: NewTestRun,
                 post_logs_mock,
                 cypress_fixturedir):
    settings.TEST = True
    testrun.project.browsers = ['chrome']

    next_spec_mock = respx_mock.post('https://api.cykubed.com/agent/testrun/20/next-spec').mock(side_effect=[
        Response(status_code=200, content='cypress/e2e/nonsense/test4.spec.ts'),
        Response(status_code=204)
    ])
    img1_path = os.path.join(cypress_fixturedir, 'dummy-sshot1.png')
    spec_completed_mock = respx_mock.post('https://api.cykubed.com/agent/testrun/20/spec-completed')
    cmdresult = mocker.Mock()
    cmdresult.returncode = 0

    testresult = TestResult(browser='chrome',
                            status=TestResultStatus.failed,
                            duration=12.5,
                            retry=1,
                            failure_screenshots=[img1_path, img1_path])

    spec_result = SpecTests(
        tests=[SpecTest(title="my title",
                        context="my context",
                        status=TestResultStatus.failed,
                        results=[testresult])])

    parse_results_mock = mocker.patch('cykubedrunner.cypress.parse_cypress_results', return_value=spec_result)
    upload_mock = respx_mock.post('https://api.cykubed.com/agent/testrun/20/upload-artifacts').mock(
        return_value=Response(200, json={'urls': ['https://api.cykubed.com/artifacts/foo.png',
                                                  'https://api.cykubed.com/artifacts/bah.png',
                                                  ]}))
    server_thread_mock = mocker.Mock()
    start_server_mock = mocker.patch('cykubedrunner.runner.start_server', return_valu=server_thread_mock)

    def create_mock_output(browser: str = None) -> bool:
        with open(f'{settings.get_results_dir()}/out.json', 'w') as f:
            f.write(json.dumps({'passed': 1}))
        return True

    # we'll need dummy node_modules and cypress_cache directories to pass the checks
    os.makedirs(os.path.join(settings.src_dir, 'node_modules'))
    os.mkdir(os.path.join(settings.BUILD_DIR, 'cypress_cache'))

    run(testrun.id)

    start_server_mock.assert_called_once()

    assert next_spec_mock.call_count == 2

    subprocess_mock.assert_called_once()

    parse_results_mock.assert_called_once()
    assert upload_mock.call_count == 1

    assert spec_completed_mock.call_count == 1
    payload = json.loads(spec_completed_mock.calls[0].request.content.decode())

    with open(os.path.join(cypress_fixturedir, 'expected-spec-completed-payload.json')) as f:
        expected = json.loads(f.read())

    assert expected == payload
