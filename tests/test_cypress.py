import datetime
import json
import os

import httpx
import pytest
from freezegun import freeze_time
from httpx import Response
from pytz import utc
from redis import Redis

from common.enums import TestResultStatus
from common.schemas import NewTestRun, SpecResult, TestResult
from cypress import run_tests, runner_stopped
from settings import settings


@freeze_time('2022-04-03 14:10:00Z')
@pytest.mark.respx(base_url="https://api.cykubed.com/agent/testrun/20")
def test_cypress(mocker, respx_mock, testrun: NewTestRun, redis: Redis,
                 fixturedir):
    redis.sadd(f'testrun:{testrun.id}:specs', 'cypress/e2e/nonsense/test4.spec.ts')

    img1_path = os.path.join(fixturedir, 'dummy-sshot1.png')
    spec_started_mock = respx_mock.post('/spec-started')
    spec_completed_mock = respx_mock.post('/spec-completed')
    cmdresult = mocker.Mock()
    cmdresult.returncode = 0
    runner_stopped(20, 120)

    # check duration
    dur = redis.get('testrun:20:runner:duration:normal')
    assert dur == '120'

    started_at = datetime.datetime(2022, 4, 3, 14, 11, 0, tzinfo=utc)
    spec_result = SpecResult(
        tests=[TestResult(title="my title",
                          context="my context",
                          status=TestResultStatus.failed,
                          duration=12.5,
                          retry=1,
                          failure_screenshots=[img1_path, img1_path],
                          started_at=started_at,
                          finished_at=started_at + datetime.timedelta(minutes=3)
                          )])
    parse_results_mock = mocker.patch('cypress.parse_results', return_value=spec_result)
    upload_mock = respx_mock.post('/artifact/upload').mock(
        return_value=Response(200, text='https://dummy-upload.cykubed.com/artifacts/blah.png'))
    httpclient = httpx.Client(base_url='https://api.cykubed.com/agent/testrun/20')
    server_thread_mock = mocker.Mock()

    def create_mock_output() -> bool:
        with open(f'{settings.get_results_dir()}/out.json', 'w') as f:
            f.write(json.dumps({'passed': 1}))
        return True

    subprocess_mock = mocker.patch('cypress.CypressSpecRunner.create_cypress_process',
                                   side_effect=create_mock_output)

    run_tests(server_thread_mock, testrun, httpclient)

    assert spec_started_mock.call_count == 1

    subprocess_mock.assert_called_once()

    parse_results_mock.assert_called_once()
    assert upload_mock.call_count == 2

    assert spec_completed_mock.call_count == 1
    payload = json.loads(spec_completed_mock.calls[0].request.content.decode())

    assert payload == {
        "file": "cypress/e2e/nonsense/test4.spec.ts",
        "finished": "2022-04-03T14:10:00+00:00",
        "result": {
            "tests": [
                {
                    "context": "my context",
                    "duration": 12,
                    "error": None,
                    "failure_screenshots": [
                        "https://dummy-upload.cykubed.com/artifacts/blah.png",
                        "https://dummy-upload.cykubed.com/artifacts/blah.png"
                    ],
                    "finished_at": "2022-04-03T14:14:00+00:00",
                    "retry": 1,
                    "started_at": "2022-04-03T14:11:00+00:00",
                    "status": "failed",
                    "title": "my title"
                }
            ],
            "video": None
        }
    }
