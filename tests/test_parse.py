import json
import os
import tempfile
from datetime import datetime
from unittest import skip
from unittest.mock import patch

import responses
from responses.matchers import multipart_matcher

import main
from common.enums import TestResultStatus
from main import parse_results

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@patch('main.RESULTS_FOLDER', FIXTURE_DIR + '/two-fails-with-retries')
def test_parse_fail():
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    assert result.file == 'test1.spec.ts'
    assert len(result.tests) == 4
    # first test passed
    test1 = result.tests[0]
    assert test1.status == TestResultStatus.passed
    assert test1.title == 'should have the correct title'
    assert test1.duration == 570
    # second test failed
    test2 = result.tests[1]
    assert test2.status == TestResultStatus.failed
    assert test2.context == 'test context'
    assert test2.title == 'this will fail'
    assert test2.duration == 4194
    assert test2.error.title == 'AssertionError'
    assert test2.error.screenshot == 'test1.spec.ts/test context -- this will fail (failed) (attempt 2).png'
    assert test2.error.message == 'Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.'
    assert test2.error.stack == '''AssertionError: Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.
    at Context.eval (webpack:///./cypress/e2e/stuff/test1.spec.ts:13:17)'''
    assert test2.error.code_frame.line == 13
    assert test2.error.code_frame.column == 18
    assert test2.error.code_frame.language == 'ts'
    assert test2.error.code_frame.frame == "  11 | \n  12 |   it('this will fail', () => {\n> 13 |     cy.get('h2').should('contain.text', 'xxx');\n     |                  ^\n  14 |   });\n  15 | \n  16 |   it.skip('this will be skipped', () => {"

    test3 = result.tests[2]
    assert test3.status == TestResultStatus.failed
    assert test3.title == 'this will also fail'
    assert test3.error.screenshot == 'test1.spec.ts/test context -- this will also fail (failed) (attempt 2).png'

    # 4th test skipped
    test4 = result.tests[3]
    assert test4.status == TestResultStatus.skipped


@patch('main.RESULTS_FOLDER', FIXTURE_DIR + '/two-fails-with-retries')
@responses.activate
def test_fetch_dist():
    responses.add(responses.GET, 'https://app.cykube.net/api/testrun/100', json={
        "id": 100,
        "branch": "master",
        "sha": "sha",
        "project": {
            "id": 40,
            "name": "dummy",
            "platform": "github",
            "url": "git@github.com:nickbrook72/dummyui.git",
            "parallelism": 4,
            "build_cmd": "ng build",
            "server_cmd": "ng serve",
            "server_port": 4200,
        },
        "total_files": 2,
        "completed_files": 0,
        "progress_percentage": 0,
        "status": "running",
        "started": "2022-05-01T15:00:12",
        "active": True
    })
    with open(FIXTURE_DIR+'/dummy-dist.tgz', 'rb') as f:
        data = f.read()

    responses.add(responses.GET, 'http://cykubehub:5003/sha.tar.lz4', body=data)
    tr = main.fetch_dist(100, 'sha', 100, 'http://cykubehub:5003')
    files = list(os.listdir(main.BUILD_DIR+'/dist'))
    assert set(files) == {'one.txt', 'two.txt'}
    assert tr.status == 'running'


@responses.activate
@patch('main.RESULTS_FOLDER', FIXTURE_DIR + '/one-fail')
@skip("Can't get responses to work for multipart")
def test_upload():
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    req_data = json.loads(result.json())
    with open(os.path.join(FIXTURE_DIR,
                           'one-fail/screenshots/test1.spec.ts/test1 -- this will fail (failed).png'), 'rb') as f:
        img = f.read()
    with open(os.path.join(FIXTURE_DIR,
                           'one-fail/videos/test1.spec.ts.mp4'), 'rb') as f:
        video = f.read()

    req_files = {'test1 -- this will fail (failed).png': img,
                 'test1.spec.ts.mp4': video}
    responses.post(url='https://app.cykube.net/testrun/100/spec-completed/200',
                   match=[multipart_matcher(req_files, data=req_data)])

    main.upload_results(100, 200, result)

