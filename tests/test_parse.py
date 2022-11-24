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


@patch('main.RESULTS_FOLDER', FIXTURE_DIR + '/one-fail')
def test_one_failed():
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    assert result.file == 'test1.spec.ts'
    assert len(result.tests) == 3
    # first test passed
    test1 = result.tests[0]
    assert test1.status == TestResultStatus.passed
    assert test1.title == 'should have the correct title'
    assert test1.duration == 640
    # second test failed
    test2 = result.tests[1]
    assert test2.status == TestResultStatus.failed
    assert test2.title == 'this will fail'
    assert test2.duration == 4229
    assert test2.error.title == 'AssertionError'
    assert test2.error.screenshot == 'test1 -- this will fail (failed).png'
    assert test2.error.message == 'Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.'
    assert test2.error.stack == 'AssertionError: Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.\n    at Context.eval (http://localhost:4200/__cypress/tests?p=cypress/integration/test1.spec.ts:107:22)'
    assert test2.error.code_frame.line == 13
    assert test2.error.code_frame.column == 18
    assert test2.error.code_frame.language == 'ts'
    assert test2.error.code_frame.frame == "  11 | \n  12 |   it('this will fail', () => {\n> 13 |     cy.get('h2').should('contain.text', 'xxx');\n     |                  ^\n  14 |   });\n  15 | \n  16 |   it.skip('this will be skipped', () => {"

    # third test skipped
    test3 = result.tests[2]
    assert test3.status == TestResultStatus.skipped


@patch('main.RESULTS_FOLDER', FIXTURE_DIR + '/one-fail')
@responses.activate
def test_fetch_dist():
    responses.add(responses.GET, 'http://cykubehub:5002/testrun/100', json={
        "id": 100,
        "status": "running",
        "server_port": 4200,
        "branch": "master",
        "url": "https://my.git.repos/blah.git",
        "parallelism": 10,
        "started": "2022-05-01T15:00:12",
        "active": True,
        "project_id": 40,
        "sha": "sha"
    })
    with open(FIXTURE_DIR+'/dummy-dist.tgz', 'rb') as f:
        data = f.read()

    responses.add(responses.GET, 'http://cykubehub:5003/sha.tgz', body=data)
    tempdir = tempfile.mkdtemp()
    os.chdir(tempdir)
    tr = main.fetch_dist(100, 'sha', 100, 'http://cykubehub:5002', 'http://cykubehub:5003')
    files = list(os.listdir(tempdir+'/build/dist'))
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

