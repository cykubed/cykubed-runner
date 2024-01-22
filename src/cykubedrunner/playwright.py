import json
import os
import re

from cykubedrunner.baserunner import BaseSpecRunner
from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.schemas import TestResult, TestResultError, CodeFrame, SpecTests, SpecTest

ansi_escape_regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class PlaywrightSpecRunner(BaseSpecRunner):

    def parse_results(self) -> SpecTests:
        specresult = SpecTests(tests=[])

        with open(self.results_file) as f:
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
                            testresult.failure_screenshots = [x['path'] for x in attachments if
                                                              x['name'] == 'screenshot']

                        errors = pwresult.get('errors')
                        if errors:
                            testresult.errors = []
                            # collate the messages from the blocks without code frames (usually just the first one)
                            msg = "\n".join([ansi_escape_regex.sub('', err['message'])
                                              for err in errors if 'location' not in err])
                            trerr = TestResultError(message=msg)
                            code_frame_errors = [err for err in errors if 'location' in err]
                            if code_frame_errors:
                                # just take the first one
                                err = code_frame_errors[0]
                                loc = err['location']
                                trerr.test_line = loc['line']
                                trerr.code_frame = CodeFrame(file=loc['file'],
                                                             line=loc['line'],
                                                             column=loc['column'],
                                                             frame=ansi_escape_regex.sub('', err['message']))
                                testresult.errors.append(trerr)

#        print(specresult.json(indent=4))
        return specresult

    def get_env(self):
        env = os.environ.copy()
        return dict(PLAYWRIGHT_JSON_OUTPUT_NAME=self.results_file,
                    PLAYWRIGHT_BROWSERS_PATH='0',
                    PATH=f'node_modules/.bin:{env["PATH"]}')

    def get_args(self, **kwargs):
        args = ['npx', 'playwright', 'test',
                '--reporter', 'json',
                '-j', '1',
                '--quiet',
                '--forbid-only',
                '--output', self.screenshots_folder]
        if self.testrun.project.runner_retries:
            args += ['--retries', f'{self.testrun.project.runner_retries}']
        args.append(self.file)
        return args

