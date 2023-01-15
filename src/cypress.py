import asyncio
import datetime
import json
import os
import shutil
import socketserver
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler
from time import time, sleep

import httpx
from httpx import HTTPError

from common.enums import TestResultStatus
from common.schemas import TestResult, TestResultError, CodeFrame, SpecResult
from common.utils import get_headers
from logs import logger
from settings import settings
from utils import runcmd, get_sync_client


class BuildFailed(Exception):
    pass


def get_screenshots_folder():
    return os.path.join(settings.RESULTS_FOLDER, 'screenshots')


def get_videos_folder():
    return os.path.join(settings.RESULTS_FOLDER, 'videos')


def init_build_dirs():
    shutil.rmtree(settings.BUILD_DIR, ignore_errors=True)
    os.makedirs(settings.BUILD_DIR)
    os.makedirs(get_videos_folder(), exist_ok=True)
    os.makedirs(get_screenshots_folder(), exist_ok=True)


async def fetch_from_cache(path: str):
    client = httpx.AsyncClient()
    with tempfile.NamedTemporaryFile(suffix='.tar.lz4', mode='wb') as outfile:
        logger.info(f'Fetch {path}')
        async with client.stream('GET', f'{settings.CACHE_URL}/{path}.tar.lz4') as response:
            async for chunk in response.aiter_bytes():
                outfile.write(chunk)

            outfile.flush()
            if not os.path.getsize(outfile.name):
                raise BuildFailed("Zero-length dist file")
            # untar
            runcmd(f'/bin/tar xf {outfile.name} -I lz4', cwd=settings.BUILD_DIR)
            logger.info(f'Unpacked {path}')


async def fetch(project_id: int, local_id: int, cache_key: str):
    """
    Fetch the node cache and distribution from the cache server
    """
    # fetch the dist
    await asyncio.gather(fetch_from_cache(cache_key),
                         fetch_from_cache(f'{project_id}/{local_id}'))


def get_env():
    env = os.environ.copy()
    env['PATH'] = f'{settings.BUILD_DIR}/node_modules/.bin:{env["PATH"]}'
    env['CYPRESS_CACHE_FOLDER'] = 'cypress_cache'
    return env


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(settings.BUILD_DIR, 'dist'), **kwargs)


class ServerThread(threading.Thread):
    def run(self):
        with socketserver.TCPServer(("", 0), Handler) as httpd:
            self.httpd = httpd
            self.port = httpd.server_address[1]
            httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()
        self.join()


def start_server() -> ServerThread:
    """
    Start the server
    :return:
    """

    server = ServerThread()
    server.start()

    # wait until it's ready
    endtime = time() + settings.SERVER_START_TIMEOUT
    logger.info("Waiting for server to be ready...")
    # wait 5 secs - trying to fetch from ng serve too soon can crash it (!)
    sleep(5)
    while True:
        ready = False
        try:
            r = httpx.get(f'http://localhost:{server.port}')
            if r.status_code == 200:
                ready = True
        except ConnectionRefusedError:
            logger.info("...connection refused to server")
            pass

        if ready:
            logger.info('Server is ready')
            return server

        if time() > endtime:
            server.stop()
            raise BuildFailed('Failed to start server')
        sleep(5)


def parse_results(started_at: datetime.datetime, spec: str) -> SpecResult:
    tests = []
    failures = 0
    with open(os.path.join(settings.RESULTS_FOLDER, 'out.json')) as f:
        rawjson = json.loads(f.read())
        for test in rawjson['tests']:
            err = test.get('err')

            if 'duration' not in test:
                continue

            result = TestResult(title=test['title'],
                                context=test['context'],
                                status=TestResultStatus.failed if err else TestResultStatus.passed,
                                retry=test['currentRetry'],
                                duration=test['duration'],
                                started_at=started_at.isoformat(),
                                finished_at=datetime.datetime.now().isoformat())

            if err:
                failures += 1
                # check for screenshots
                sshot_fnames = []
                for root, dirs, files in os.walk(get_screenshots_folder()):
                    sshot_fnames += [os.path.join(root, f) for f in files]

                suffix = '' if not result.retry else f' (attempt {result.retry + 1})'
                expected = f'{result.context} -- {result.title} (failed){suffix}.png'

                failure_sshot = None
                for fname in sshot_fnames:
                    if os.path.split(fname)[-1] == expected:
                        failure_sshot = fname
                        break

                frame = err['codeFrame']
                result.error = TestResultError(title=err['name'],
                                               type=err['type'],
                                               message=err['message'],
                                               stack=err['stack'],
                                               screenshot=failure_sshot,
                                               code_frame=CodeFrame(line=frame['line'],
                                                                    column=frame['column'],
                                                                    language=frame['language'],
                                                                    frame=frame['frame']))

            tests.append(result)

    # add skipped
    for skipped in rawjson.get('pending', []):
        tests.append(TestResult(status=TestResultStatus.skipped,
                                context=skipped['context'],
                                title=skipped['title']))

    result = SpecResult(file=spec, tests=tests)
    # we should have a single video - but only add it if we have failures
    if failures:
        video_fnames = []
        for root, dirs, files in os.walk(get_videos_folder()):
            video_fnames += [os.path.join(root, f) for f in files]

        if video_fnames:
            result.video = video_fnames[0]
    return result


def run_cypress(file: str, port: int):
    logger.info(f'Run Cypress for {file}')
    results_file = f'{settings.RESULTS_FOLDER}/out.json'
    base_url = f'http://localhost:{port}'
    json_reporter = os.path.abspath('json-reporter.js')
    result = subprocess.run(['cypress', 'run', '-s', file, '-q',
                             f'--reporter={json_reporter}',
                             '-o', f'output={results_file}',
                             '-c', f'screenshotsFolder={get_screenshots_folder()},screenshotOnRunFailure=true,'
                                   f'baseUrl={base_url},video=true,videosFolder={get_videos_folder()}'],
                            timeout=settings.CYPRESS_RUN_TIMEOUT, capture_output=True, env=get_env(), cwd=settings.BUILD_DIR)

    logger.info(result.stdout.decode('utf8'))
    if result.returncode and result.stderr and not os.path.exists(results_file):
        logger.error('Cypress run failed: ' + result.stderr.decode())


def upload_results(spec_id, result: SpecResult):

    upload_url = f'{settings.MAIN_API_URL}/agent/testrun/upload'

    with get_sync_client() as client:
        for test in result.tests:
            if test.error:
                sshot = test.error.screenshot
                if sshot:
                    # this will be the full path - we'll upload the file but just use the filename
                    filename = os.path.split(sshot)[-1]
                    logger.info(f'Upload screenshot {filename}')
                    r = client.post(upload_url, files={'file': (sshot, open(sshot, 'rb'), 'image/png')},
                                  headers={'filename': filename})
                    if r.status_code != 200:
                        # TODO retry?
                        raise BuildFailed(f'Failed to upload screenshot to cykube: {r.status_code}')

                    test.error.screenshot = r.text

        if result.video:
            filename = os.path.split(result.video)[-1]
            logger.info(f'Upload video {filename}')
            r = client.post(upload_url, files={'file': (result.video, open(result.video, 'rb'), 'video/mp4')},
                              headers={'filename': filename})
            if r.status_code != 200:
                raise BuildFailed(f'Failed to upload video to cykube: {r.status_code}')
            result.video = r.text

        # finally upload result
        try:
            logger.info(f'Upload JSON results')
            r = client.post(f'{settings.MAIN_API_URL}/agent/testrun/spec/{spec_id}/completed',
                                  data=result.json().encode('utf8'))
            if not r.status_code == 200:
                raise BuildFailed(f'Test result post failed: {r.status_code}')
        except HTTPError:
            raise BuildFailed(f'Failed to contact Cykube server')


def run_tests(project_id: int, local_id: int, port: int):

    while True:

        r = httpx.get(f'{settings.MAIN_API_URL}/agent/testrun/{project_id}/{local_id}/next', headers=get_headers())
        if r.status_code == 204:
            # we're done
            break
        elif r.status_code == 200:
            # run the test
            spec = r.json()
            try:
                started_at = datetime.datetime.now()
                run_cypress(spec['file'], port)
                result = parse_results(started_at, spec['file'])
                upload_results(spec['id'], result)
                # cleanup
                shutil.rmtree(settings.RESULTS_FOLDER, ignore_errors=True)

            except subprocess.CalledProcessError as ex:
                raise BuildFailed(f'Cypress run failed with return code {ex.returncode}')
            except subprocess.TimeoutExpired:
                raise BuildFailed("Exceeded run timeout")
        else:
            raise BuildFailed(f"Received unexpected status code from hub: {r.status_code}")


def start(project_id: int, local_id: int, cache_key: str):
    init_build_dirs()
    # fetch the distribution
    asyncio.run(fetch(project_id, local_id, cache_key))
    # start the server
    server = start_server()

    try:
        # now fetch specs until we're done or the build is cancelled
        logger.info(f"Server running on port {server.port}")
        run_tests(project_id, local_id, server.port)
    except BuildFailed as ex:
        # TODO inform the server
        logger.exception(ex)
    finally:
        # kill the server
        server.stop()
