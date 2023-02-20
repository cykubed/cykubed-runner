import os

import pytest
from httpx import Response

from common.schemas import SpecResult
from common.settings import settings
from cypress import run_tests


@pytest.mark.respx
def test_run_tests(respx_mock, mocker, testrun, fixturedir):
    settings.RESULTS_FOLDER = os.path.join(fixturedir, 'results/test1')

    def next_spec_side_effect(request, route):
        if route.call_count == 0:
            return Response(200, text='cypress/e2e/stuff/test1.spec.ts')
        return Response(204)

    next_spec_mock = respx_mock.get('http://127.0.0.1:5000/testrun/20/next')\
        .mock(side_effect=next_spec_side_effect)

    cypressrun = mocker.patch('subprocess.run')

    def upload_side_effect(request, route):
        return Response(200, text=f'https://cykube.com/sshot{route.call_count}.png')

    upload_file = respx_mock.post(f'{settings.MAIN_API_URL}/agent/testrun/upload').mock(
        side_effect=upload_side_effect
    )
    spec_completed = respx_mock.post(f'{settings.AGENT_URL}/testrun/20/spec-completed')

    run_tests(20, 2400)

    assert next_spec_mock.call_count == 2
    cypressrun.assert_called_once()
    assert upload_file.call_count == 6
    assert spec_completed.call_count == 1
    payload = spec_completed.calls[0].request.content.decode()
    result = SpecResult.parse_raw(payload)
    assert result.file == "cypress/e2e/stuff/test1.spec.ts"
    assert len(result.tests) == 5

    test0 = result.tests[0]
    assert test0.title == 'should have the correct title'
    assert test0.status == 'passed'
    assert test0.failure_screenshots is None

    test1 = result.tests[1]
    assert test1.title == 'this will fail'
    assert test1.status == 'failed'
    assert test1.retry == 1
    assert test1.failure_screenshots == ['https://cykube.com/sshot0.png',
                                         'https://cykube.com/sshot1.png',
                                         ]
    assert test1.error.title == 'AssertionError'
    assert test1.error.type == 'existence'
    assert test1.error.message == 'Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.'

    # etc...
