import os
from datetime import datetime

from common.enums import TestResultStatus
from cypress import parse_results


def test_parse_fail(mocker, fixturedir):
    mocker.patch('settings.RunnerSettings.get_results_dir',
                 return_value=os.path.join(fixturedir, 'two-fails-with-retries'))

    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), "cypress/e2e/stuff/test1.spec.ts")
    # these will be the full paths
    sshotdir = os.path.join(fixturedir, 'two-fails-with-retries', 'screenshots')
    viddir = os.path.join(fixturedir, 'two-fails-with-retries', 'videos')
    assert result.video == os.path.join(viddir, 'test1.spec.ts.mp4')
    assert len(result.tests) == 3
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
    assert set(test2.failure_screenshots) == {
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will fail (failed).png'),
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will fail (failed) (attempt 2).png')}

    assert test2.error.message == 'Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.'
    assert test2.error.stack == '''AssertionError: Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.
    at Context.eval (webpack:///./cypress/e2e/stuff/test1.spec.ts:13:17)'''
    assert test2.error.code_frame.line == 13
    assert test2.error.test_line == 13
    assert test2.error.code_frame.column == 18
    assert test2.error.code_frame.language == 'ts'
    assert test2.error.code_frame.frame == "  11 | \n  12 |   it('this will fail', () => {\n> 13 |     cy.get('h2').should('contain.text', 'xxx');\n     |                  ^\n  14 |   });\n  15 | \n  16 |   it.skip('this will be skipped', () => {"

    test3 = result.tests[2]
    assert test3.status == TestResultStatus.failed
    assert test3.title == 'this will also fail'
    assert set(test3.failure_screenshots) == {
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will also fail (failed).png'),
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will also fail (failed) (attempt 2).png')}


def test_parse_fail_inside_helper(mocker, fixturedir):
    """
    If the test fails inside a helper function then record the original line number
    """
    mocker.patch('settings.RunnerSettings.get_results_dir',
                 return_value=os.path.join(fixturedir, 'fail-inside-helper'))
    result = parse_results(datetime(2022, 11, 23, 13, 0, 0), 'cypress/e2e/stuff/test1.spec.ts')
    assert len(result.tests) == 3
    test = result.tests[2]
    assert test.error.code_frame.line == 6
    assert test.error.test_line == 21
