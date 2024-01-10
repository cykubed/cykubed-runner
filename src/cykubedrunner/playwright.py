import json

from dateutil.parser import parse

from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.schemas import TestResult, TestResultError, CodeFrame, SpecTests, SpecTest, \
    SpecTestBrowserResults


def parse_playwright_results(json_file: str) -> SpecTests:
    specresult = SpecTests(tests=[])

    with open(json_file) as f:
        rawjson = json.loads(f.read())

    # first group by line
    byline = dict()
    for suite in rawjson['suites']:
        for spec in suite['specs']:
            byline.setdefault(spec['line'], []).append(spec)

    for specs in byline.values():
        # these will all have the same title
        failed = any([not x['ok'] for x in specs])
        spectest = SpecTest(title=specs[0]['title'],
                            line=specs[0]['line'],
                            browser_results=[],
                            status=TestResultStatus.passed if failed else TestResultStatus.failed)
        specresult.tests.append(spectest)
        for spec in specs:
            if spec['tests']:

                bybrowser = SpecTestBrowserResults(browser=spec['tests'][0]['projectName'],
                                                   results=[])
                spectest.browser_results.append(bybrowser)
                for test in spec['tests']:

                    for pwresult in test['results']:
                        testresult = TestResult(
                            status=TestResultStatus.passed if pwresult['status'] == 'passed' else
                                                TestResultStatus.failed)
                        bybrowser.results.append(testresult)
                        testresult.retry = pwresult['retry']
                        testresult.duration = pwresult['duration']
                        testresult.started_at = parse(pwresult['startTime'])

                        attachments = pwresult.get('attachments')
                        if attachments:
                            testresult.failure_screenshots = [x['path'] for x in attachments]

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
