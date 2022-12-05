import os
from datetime import datetime
from unittest.mock import patch

import respx
from httpx import Response

import main
from main import parse_results

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@respx.mock
async def test_fetch_dist(testrun):
    tr_route = respx.get('https://app.cykube.net/api/testrun/100').mock(return_value=Response(200, json=testrun))
    with open(FIXTURE_DIR+'/dummy-dist.tgz', 'rb') as f:
        data = f.read()
    cache_route = respx.get('http://127.0.0.1:5001/sha.tar.lz4')\
        .mock(return_value=Response(200, content=data))
    await main.fetch_dist(100)
    assert tr_route.called
    assert cache_route.called
    files = list(os.listdir(main.BUILD_DIR+'/dist'))
    assert set(files) == {'one.txt', 'two.txt'}


@respx.mock
@patch('main.RESULTS_FOLDER', FIXTURE_DIR + '/two-fails-with-retries')
async def test_upload_results():
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    upload_route = respx.post('https://app.cykube.net/api/hub/testrun/spec/10/upload') % 200
    completed_route = respx.post('https://app.cykube.net/api/hub/testrun/spec/10/completed')\
        .mock(return_value=Response(200, json=result.json()))
    await main.upload_results(10, result)
    assert upload_route.call_count == 3
    assert completed_route.called

