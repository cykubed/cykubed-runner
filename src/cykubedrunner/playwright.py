import datetime
import json
import os

from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.common.schemas import TestResult, TestResultError, CodeFrame, SpecResult, SpecTest, \
    SpecTestBrowserResults
from cykubedrunner.settings import settings


def parse_playwright_results() -> SpecResult:
    specresult = SpecResult(tests=[])

    with open(os.path.join(settings.get_results_dir(), 'out.json')) as f:
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
                            results=[],
                            status=TestResultStatus.passed if failed else TestResultStatus.failed)
        specresult.tests.append(spectest)
        for spec in specs:
            if spec['tests']:
                bybrowser = SpecTestBrowserResults(browser=spec['tests'][0]['projectName'],
                                                   results=[])
                spectest.results.append(bybrowser)
                for spectest in spec['tests']:
                    testresult = TestResult(
                        browser=spectest['projectName'],
                        status=TestResultStatus.passed if spectest['status'] == 'passed' else
                                            TestResultStatus.failed)
                    bybrowser.results.append(testresult)

                    for pwresult in spectest['results']:
                        testresult.retry = pwresult['retry']
                        testresult.duration = pwresult['duration']
                        testresult.started_at = datetime.datetime.fromisoformat(pwresult['startTime'])
                        spectest.results.append(testresult)

                        if spectest['errors']:
                            testresult.errors = []
                            for error in spectest['errors']:
                                trerr = TestResultError(message=error['message'])
                                loc = error.get('location')
                                if loc:
                                    trerr.code_frame = CodeFrame(file=loc['file'],
                                                                 line=loc['line'],
                                                                 column=loc['column'])
                                testresult.errors.append(trerr)

                    attachments = spectest.get('attachments')
                    if attachments:
                        testresult.failure_screenshots = [x['path'] for x in attachments]
    return specresult
