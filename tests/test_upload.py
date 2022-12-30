import os
from datetime import datetime

import httpx
import pytest
import respx
from httpx import Response

from cypress import parse_results, upload_results, fetch_dist, BuildFailed
from settings import settings

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@respx.mock
async def test_fetch_dist_poll(testrun):
    settings.HUB_POLL_PERIOD = 0.1
    settings.DIST_BUILD_TIMEOUT = 0.1
    testrun['status'] = 'building'
    tr_route = respx.get('http://127.0.0.1:5000/testrun/100').mock(return_value=Response(200, json=testrun))
    cache_route = respx.get('http://127.0.0.1:5001/sha.tar.lz4')
    with pytest.raises(BuildFailed):
        await fetch_dist(100)
    assert tr_route.called
    assert not cache_route.called


@respx.mock
async def test_fetch_dist(testrun):
    tr_route = respx.get('http://127.0.0.1:5000/testrun/100').mock(return_value=Response(200, json=testrun))
    with open(FIXTURE_DIR+'/dummy-dist.tar.lz4', 'rb') as f:
        data = f.read()
    cache_route = respx.get('http://127.0.0.1:5001/sha.tar.lz4')\
        .mock(return_value=Response(200, content=data))
    await fetch_dist(100)
    assert tr_route.called
    assert cache_route.called
    files = list(os.listdir(os.path.join(settings.BUILD_DIR, 'dist')))
    assert set(files) == {'one.txt', 'two.txt'}


@respx.mock
async def test_upload_results():
    settings.RESULTS_FOLDER = os.path.join(FIXTURE_DIR, 'two-fails-with-retries')
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    upload_route = respx.post('https://app.cykube.net/api/agent/testrun/upload').mock(
        return_value=httpx.Response(200, text='anewpath.png'))
    completed_route = respx.post('https://app.cykube.net/api/agent/testrun/spec/10/completed')\
        .mock(return_value=Response(200, json=result.json()))
    await upload_results(10, result)
    assert result.tests[1].error.screenshot == 'anewpath.png'
    # in fact all paths will be set to this
    assert result.video == 'anewpath.png'
    assert upload_route.call_count == 3
    assert completed_route.called

