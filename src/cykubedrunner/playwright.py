import json

from dateutil.parser import parse

from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.schemas import TestResult, TestResultError, CodeFrame, SpecTests, SpecTest


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
        spectest = SpecTest(title=specs[0]['title'],
                            line=specs[0]['line'],
                            results=[],
                            status=TestResultStatus.passed)
        specresult.tests.append(spectest)
        for spec in specs:
            if spec['tests']:
                for test in spec['tests']:
                    for pwresult in test['results']:

                        status=TestResultStatus.passed if pwresult['status'] == 'passed' else \
                                                        TestResultStatus.failed
                        if status == TestResultStatus.failed:
                            spectest.status = TestResultStatus.failed

                        testresult = TestResult(
                            browser=test['projectName'],
                            status=status)

                        spectest.results.append(testresult)
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
