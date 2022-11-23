import os
from datetime import datetime
from pprint import pprint
from unittest import mock
from unittest.mock import patch

import main
from common.enums import TestResultStatus
from main import parse_results

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@patch('main.RESULTS_FOLDER', FIXTURE_DIR+'/one-fail')
def test_one_failed():
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    assert len(result.tests) == 2
    # first test passed
    test1 = result.tests[0]
    assert test1.status == TestResultStatus.passed
    assert test1.title == 'should have the correct title'
    assert test1.duration == 708
    # second test failed
    test2 = result.tests[1]
    assert test2.status == TestResultStatus.failed
    assert test2.title == 'this will fail'
    assert test2.duration == 4173
    assert test2.error.title == 'AssertionError'
