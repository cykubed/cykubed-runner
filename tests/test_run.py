import os

import pytest
from httpx import Response

from common.enums import AgentEventType
from mongo import runs_coll, specs_coll, messages_coll
from common.schemas import SpecResult, AgentSpecStarted, AgentSpecCompleted
from common.settings import settings
from cypress import run_tests


@pytest.mark.respx
def test_run_tests(respx_mock, mocker, testrun, fixturedir):
    settings.RESULTS_FOLDER = os.path.join(fixturedir, 'results/test1')
    testrun.status = 'running'
    runs_coll().insert_one(testrun.dict())

    # single spec
    specs_coll().insert_one({'trid': 20, 'file': 'cypress/e2e/stuff/test1.spec.ts'})

    # mock the actual Cypress run
    cypressrun = mocker.patch('subprocess.run')

    def upload_side_effect(request, route):
        return Response(200, text=f'https://cykube.com/sshot{route.call_count}.png')

    upload_file = respx_mock.post(f'{settings.MAIN_API_URL}/agent/testrun/upload').mock(
        side_effect=upload_side_effect
    )

    run_tests(testrun, 2400)

    # the spec will be finished
    spec = specs_coll().find_one()
    assert spec['finished'] is not None

    # we'll have two messages for the agent: a spec_started and a spec_completed
    msgs = list(messages_coll().find())
    assert len(msgs) == 2
    msg0 = AgentSpecStarted.parse_raw(msgs[0]['msg'])
    assert msg0.type == AgentEventType.spec_started
    assert msg0.testrun_id == 20
    assert msg0.file == 'cypress/e2e/stuff/test1.spec.ts'
    msg1 = AgentSpecCompleted.parse_raw(msgs[1]['msg'])
    assert msg1.type == AgentEventType.spec_completed
    assert msg1.testrun_id == 20
    assert msg1.file == 'cypress/e2e/stuff/test1.spec.ts'

    # a 6 artifacts will have been uploaded to the main server
    cypressrun.assert_called_once()
    assert upload_file.call_count == 6

    result = SpecResult.parse_obj(spec['result'])
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
