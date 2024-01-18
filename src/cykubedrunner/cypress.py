import datetime
import json
import os

from cykubedrunner.baserunner import BaseSpecRunner
from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.exceptions import RunFailedException
from cykubedrunner.common.schemas import SpecTests, TestResult, SpecTest, CodeFrame, TestResultError, \
    NewTestRun
from cykubedrunner.server import ServerThread
from cykubedrunner.settings import settings
from cykubedrunner.utils import logger


class CypressSpecRunner(BaseSpecRunner):

    def __init__(self, server: ServerThread,
                 testrun: NewTestRun, file: str, browser):
        super().__init__(server, testrun, file)
        self.browser = browser
        srccypress = os.path.join(settings.BUILD_DIR, 'cypress_cache')
        if not os.path.exists(srccypress):
            raise RunFailedException("Missing cypress cache folder")

    def parse_results(self) -> SpecTests:
        failures = 0
        specresult = SpecTests(tests=[])

        with open(self.results_file) as f:
            rawjson = json.loads(f.read())

            sshot_fnames = []
            for root, dirs, files in os.walk(self.screenshots_folder):
                sshot_fnames += [os.path.join(root, f) for f in files]

            for test in rawjson['tests']:
                err = test.get('err')

                if 'duration' not in test:
                    continue
                title, context = test['title'], test['context']

                result = TestResult(status=TestResultStatus.failed if err else TestResultStatus.passed,
                                    browser=self.browser,
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
                        if 'relativeFile' in parsed and parsed['relativeFile'].endswith(self.file):
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

        # we should have a single  - but only add it if we have failures
        if failures:
            video_fnames = []
            for root, dirs, files in os.walk(self.videos_folder):
                video_fnames += [os.path.join(root, f) for f in files]

            if video_fnames:
                specresult.video = video_fnames[0]
        return specresult

    def get_args(self, browser=None):
        json_reporter = os.path.abspath(os.path.join(os.path.dirname(__file__), 'json-reporter.js'))

        return ['cypress', 'run',
                '-q',
                '--browser', browser or 'electron',
                '-s', self.file,
                '--reporter', json_reporter,
                '-o', f'output={self.results_file}',
                '-c', f'screenshotsFolder={self.screenshots_folder},screenshotOnRunFailure=true,'
                      f'baseUrl={self.base_url},video=false,videosFolder={self.videos_folder}']

    def get_env(self):
        env = os.environ.copy()
        env.update(CYPRESS_CACHE_FOLDER=f'{settings.BUILD_DIR}/cypress_cache',
                   PATH=f'node_modules/.bin:{env["PATH"]}')

        if self.testrun.project.runner_retries:
            env['CYPRESS_RETRIES'] = str(self.testrun.project.runner_retries)
        return env
