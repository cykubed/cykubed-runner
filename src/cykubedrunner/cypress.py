import datetime
import json
import os
import subprocess

from cykubedrunner.app import app
from cykubedrunner.baserunner import BaseSpecRunner
from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.exceptions import RunFailedException
from cykubedrunner.common.schemas import SpecTests, TestResult, SpecTest, CodeFrame, TestResultError, AgentSpecCompleted
from cykubedrunner.common.utils import utcnow
from cykubedrunner.settings import settings
from cykubedrunner.utils import logger, upload_results


def parse_cypress_results(json_file: str, browser: str, spec_file: str) -> SpecTests:
    failures = 0
    specresult = SpecTests(tests=[])

    with open(json_file) as f:
        rawjson = json.loads(f.read())

        sshot_fnames = []
        for root, dirs, files in os.walk(settings.get_screenshots_folder()):
            sshot_fnames += [os.path.join(root, f) for f in files]

        for test in rawjson['tests']:
            err = test.get('err')

            if 'duration' not in test:
                continue
            title, context = test['title'], test['context']

            result = TestResult(status=TestResultStatus.failed if err else TestResultStatus.passed,
                                browser=browser,
                                retry=test['currentRetry'],
                                duration=test['duration'],
                                finished_at=datetime.datetime.now().isoformat())

            if result.status == TestResultStatus.passed and result.retry:
                # flakey
                result.status = TestResultStatus.flakey

            spectest = SpecTest(results=[result],
                                title=title,
                                context=context,
                                status=result.status)

            # check for screenshots
            prefix = f'{context} -- {title} (failed)'
            sshots = []
            for fname in sshot_fnames:
                if os.path.split(fname)[-1].startswith(prefix):
                    sshots.append(fname)
            if sshots:
                result.failure_screenshots = sshots

            if err:
                failures += 1
                frame = err.get('codeFrame')
                if not frame:
                    fullerror = json.dumps(err)
                    logger.warning(f"No code frame: full error: {fullerror}")
                else:
                    codeframe = CodeFrame(line=frame['line'],
                                          file=frame['relativeFile'],
                                          column=frame['column'],
                                          language=frame['language'],
                                          frame=frame['frame'])
                # get line number of test
                testline = 0
                for parsed in err['parsedStack']:
                    if 'relativeFile' in parsed and parsed['relativeFile'].endswith(spec_file):
                        testline = parsed['line']
                        break

                try:
                    result.errors = [TestResultError(title=err['name'],
                                                   type=err.get('type'),
                                                   test_line=testline,
                                                   message=err['message'],
                                                   stack=err['stack'],
                                                   code_frame=codeframe)]
                except:
                    raise RunFailedException("Failed to parse test result")

            specresult.tests.append(spectest)

    # we should have a single video - but only add it if we have failures
    if failures:
        video_fnames = []
        for root, dirs, files in os.walk(settings.get_videos_folder()):
            video_fnames += [os.path.join(root, f) for f in files]

        if video_fnames:
            specresult.video = video_fnames[0]
    return specresult


class CypressSpecRunner(BaseSpecRunner):

    def get_args(self, browser=None):
        base_url = f'http://localhost:{self.server.port}'
        json_reporter = os.path.abspath(os.path.join(os.path.dirname(__file__), 'json-reporter.js'))

        return ['cypress', 'run',
                '-q',
                '--browser', browser or 'electron',
                '-s', self.file,
                '--reporter', json_reporter,
                '-o', f'output={self.results_file}',
                '-c', f'screenshotsFolder={settings.get_screenshots_folder()},screenshotOnRunFailure=true,'
                      f'baseUrl={base_url},video=false,videosFolder={settings.get_videos_folder()}']

    def get_env(self):
        env = os.environ.copy()
        env.update(CYPRESS_CACHE_FOLDER=f'{settings.BUILD_DIR}/cypress_cache',
                   PATH=f'node_modules/.bin:{env["PATH"]}')

        if self.testrun.project.cypress_retries:
            env['CYPRESS_RETRIES'] = str(self.testrun.project.cypress_retries)
        return env

    def run(self):
        self.started = utcnow()
        logger.debug(f'Run Cypress for {self.file}')
        try:
            spectests = None
            for browser in self.testrun.project.browsers or ['electron']:
                proc = self.create_process(browser)
                if not os.path.exists(self.results_file):
                    if proc.returncode == 1:
                        # there was a problem with the run - log output
                        logger.error(f"Cypress run failed to produce any results:\n {proc.stdout}\n{proc.stderr}")
                    raise RunFailedException(f'Missing results file')

                # parse the results
                json_file = os.path.join(settings.get_results_dir(), 'out.json')
                result = parse_cypress_results(json_file,
                                               browser,
                                               self.file)
                if not spectests:
                    spectests = result
                else:
                    # merge
                    spectests.merge(result)
            if spectests:
                upload_results(self.file, spectests)
        except subprocess.TimeoutExpired:
            logger.info(f'Exceeded deadline for spec {self.file}')

            r = app.http_client.post('/spec-completed',
                                     content=AgentSpecCompleted(
                                         result=SpecTests(timeout=True, tests=[]),
                                         file=self.file,
                                         finished=utcnow()).json())
            if r.status_code != 200:
                raise RunFailedException(f'Failed to set spec completed: {r.status_code}: {r.text}')
