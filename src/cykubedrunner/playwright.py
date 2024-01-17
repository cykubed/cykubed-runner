import json

from cykubedrunner.baserunner import BaseSpecRunner
from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.schemas import TestResult, TestResultError, CodeFrame, SpecTests, SpecTest
from cykubedrunner.settings import settings


def parse_playwright_results(json_file: str) -> SpecTests:
    specresult = SpecTests(tests=[])

    with open(json_file) as f:
        rawjson = json.loads(f.read())

    # first group by line
    byline = dict()
    for suite in rawjson['suites']:
        for spec in suite['specs']:
            if spec['ok'] and spec['tests'] and spec['tests'][0]['status'] == 'skipped':
                continue
            byline.setdefault(spec['line'], []).append(spec)

    for specs in byline.values():
        # these will all have the same title
        spectest = SpecTest(title=specs[0]['title'],
                            line=specs[0]['line'],
                            results=[],
                            status=TestResultStatus.passed)
        specresult.tests.append(spectest)
        for spec in specs:
            if not spec['ok']:
                spectest.status = TestResultStatus.failed

            if spec['tests']:
                test = spec['tests'][0]

                if test['status'] == 'skipped':
                    continue
                if test['status'] == 'flaky' and spec['ok']:
                    spectest.status = TestResultStatus.flakey

                for pwresult in test['results']:

                    status = TestResultStatus.passed if pwresult['status'] == 'passed' else \
                                                    TestResultStatus.failed

                    testresult = TestResult(
                        browser=test['projectName'],
                        status=status)

                    spectest.results.append(testresult)

                    testresult.retry = pwresult['retry']
                    testresult.duration = pwresult['duration']

                    attachments = pwresult.get('attachments')
                    if attachments:
                        testresult.failure_screenshots = [x['path'] for x in attachments if x['name'] == 'screenshot']

                    errors = pwresult.get('errors')
                    if errors:
                        testresult.errors = []
                        for error in errors:
                            trerr = TestResultError(message=error['message'])
                            loc = error.get('location')
                            if loc:
                                trerr.test_line = loc['line']
                                trerr.code_frame = CodeFrame(file=loc['file'],
                                                             line=loc['line'],
                                                             column=loc['column'])
                            testresult.errors.append(trerr)
    return specresult


class PlaywrightSpecRunner(BaseSpecRunner):

    def get_env(self):
        return dict(PLAYWRIGHT_JSON_OUTPUT_NAME=self.results_file)

    def get_args(self, **kwargs):
        args = ['npx', 'playwright', 'test',
                '--reporter', 'json',
                '-j', '1',
                '--quiet',
                '--forbid-only',
                '--output', settings.get_screenshots_folder()]
        if self.testrun.project.runner_retries:
            args += ['--retries', self.testrun.project.runner_retries]
        args.append(self.file)
        return args

