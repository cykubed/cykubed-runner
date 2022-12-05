import os
from datetime import datetime
from unittest.mock import patch

from common.enums import TestResultStatus
from main import parse_results

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@patch('main.RESULTS_FOLDER', FIXTURE_DIR + '/two-fails-with-retries')
def test_parse_fail():
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'test1.spec.ts')
    assert result.video == 'test1.spec.ts.mp4'
    assert result.file == 'test1.spec.ts'
    assert len(result.tests) == 4
    # first test passed
    test1 = result.tests[0]
    assert test1.status == TestResultStatus.passed
    assert test1.title == 'should have the correct title'
    # second test failed
    test2 = result.tests[1]
    assert test2.status == TestResultStatus.failed
    assert test2.context == 'test context'
    assert test2.title == 'this will fail'
    assert test2.error.title == 'AssertionError'
    assert test2.error.screenshot == 'test1.spec.ts/test context -- this will fail (failed) (attempt 2).png'
    assert test2.error.message == 'Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.'
    assert test2.error.stack == '''AssertionError: Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.
    at Context.eval (webpack:///./cypress/e2e/stuff/test1.spec.ts:13:17)'''
    assert test2.error.code_frame.line == 13
    assert test2.error.code_frame.column == 18
    assert test2.error.code_frame.language == 'ts'
    assert test2.error.code_frame.frame == "  11 | \n  12 |   it('this will fail', () => {\n> 13 |     cy.get('h2').should('contain.text', 'xxx');\n     |                  ^\n  14 |   });\n  15 | \n  16 |   it.skip('this will be skipped', () => {"

    test3 = result.tests[2]
    assert test3.status == TestResultStatus.failed
    assert test3.title == 'this will also fail'
    assert test3.error.screenshot == 'test1.spec.ts/test context -- this will also fail (failed) (attempt 2).png'

    # 4th test skipped
    test4 = result.tests[3]
    assert test4.status == TestResultStatus.skipped


