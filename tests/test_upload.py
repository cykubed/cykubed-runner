import os
import tempfile
from datetime import datetime
from http.server import SimpleHTTPRequestHandler

import httpx
import respx
from httpx import Response
from pytest_httpserver import HTTPServer

from common.settings import settings
from cypress import parse_results, upload_results, fetch

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FIXTURE_DIR, **kwargs)


def test_fetch_dist(testrun, httpserver: HTTPServer):
    builddir = tempfile.mkdtemp()
    settings.CACHE_URL = 'http://localhost:5300'
    settings.BUILD_DIR = builddir
    httpserver.expect_oneshot_request('/deadbeef0101.tar.lz4')\
        .respond_with_data(open(FIXTURE_DIR+'/deadbeef0101.tar.lz4', 'rb').read())
    httpserver.expect_oneshot_request('/1-20.tar.lz4')\
        .respond_with_data(open(FIXTURE_DIR+'/1-20.tar.lz4', 'rb').read())
    fetch(1, 20, 'deadbeef0101')
    files = list(os.listdir(os.path.join(builddir, 'dist')))
    assert set(files) == {'one.txt', 'two.txt'}
    rootfiles = set(os.listdir(os.path.join(builddir)))
    assert 'node_modules' in rootfiles
    assert 'cypress_cache' in rootfiles


@respx.mock
async def test_upload_results():
    settings.RESULTS_FOLDER = os.path.join(FIXTURE_DIR, 'two-fails-with-retries')
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    upload_route = respx.post('https://app.cykube.net/api/agent/testrun/upload').mock(
        return_value=httpx.Response(200, text='anewpath.png'))
    completed_route = respx.post('https://app.cykube.net/api/agent/testrun/spec/10/completed')\
        .mock(return_value=Response(200, json=result.json()))
    upload_results(10, result)
    # 5 uploads: 4 images and one video
    assert upload_route.call_count == 5
    assert completed_route.called

