import os

from cykubedrunner.common.enums import TestResultStatus
from cykubedrunner.cypress import parse_cypress_results


def test_cypress_parse_fail(mocker, cypress_fixturedir):
    mocker.patch('cykubedrunner.settings.RunnerSettings.get_results_dir',
                 return_value=os.path.join(cypress_fixturedir, 'two-fails-with-retries'))

    jsonfile = os.path.join(cypress_fixturedir, 'two-fails-with-retries/out.json')

    result = parse_cypress_results(jsonfile, 'electron',
                                   "cypress/e2e/stuff/test1.spec.ts")
    # these will be the full paths
    sshotdir = os.path.join(cypress_fixturedir, 'two-fails-with-retries', 'screenshots')
    viddir = os.path.join(cypress_fixturedir, 'two-fails-with-retries', 'videos')
    assert result.video == os.path.join(viddir, 'test1.spec.ts.mp4')
    assert len(result.tests) == 3
    # first test passed
    test1 = result.tests[0]
    assert test1.status == TestResultStatus.passed
    assert test1.title == 'should have the correct title'
    assert len(test1.browser_results) == 1
    browser_results = test1.browser_results[0]
    assert browser_results.browser == 'electron'
    assert len(browser_results.results) == 1

    # second test failed
    test2 = result.tests[1]
    assert test2.status == TestResultStatus.failed
    assert test2.context == 'test context'
    assert test2.title == 'this will fail'
    assert len(test2.browser_results) == 1
    browser_results = test2.browser_results[0]
    assert len(browser_results.results) == 1
    result1 = browser_results.results[0]
    error = result1.errors[0]
    assert error.title == 'AssertionError'
    assert set(result1.failure_screenshots) == {
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will fail (failed).png'),
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will fail (failed) (attempt 2).png')}

    assert error.message == 'Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.'
    assert error.stack == '''AssertionError: Timed out retrying after 4000ms: Expected to find element: `h2`, but never found it.
    at Context.eval (webpack:///./cypress/e2e/stuff/test1.spec.ts:13:17)'''
    assert error.code_frame.line == 13
    assert error.test_line == 13
    assert error.code_frame.column == 18
    assert error.code_frame.language == 'ts'
    assert error.code_frame.frame == "  11 | \n  12 |   it('this will fail', () => {\n> 13 |     cy.get('h2').should('contain.text', 'xxx');\n     |                  ^\n  14 |   });\n  15 | \n  16 |   it.skip('this will be skipped', () => {"

    test3 = result.tests[2]
    assert test3.status == TestResultStatus.failed
    assert test3.title == 'this will also fail'
    assert len(test3.browser_results) == 1
    assert len(test3.browser_results[0].results) == 1
    assert set(test3.browser_results[0].results[0].failure_screenshots) == {
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will also fail (failed).png'),
        os.path.join(sshotdir, 'stuff/test1.spec.ts/test context -- this will also fail (failed) (attempt 2).png')}


def test_cypress_parse_fail_inside_helper(mocker, cypress_fixturedir):
    """
    If the test fails inside a helper function then record the original line number
    """
    mocker.patch('cykubedrunner.settings.RunnerSettings.get_results_dir',
                 return_value=os.path.join(cypress_fixturedir, 'fail-inside-helper'))

    jsonfile = os.path.join(cypress_fixturedir, 'fail-inside-helper/out.json')

    result = parse_cypress_results(jsonfile, 'chrome',
                                    'cypress/e2e/stuff/test1.spec.ts')
    assert len(result.tests) == 3
    test = result.tests[2]
    assert len(test.browser_results) == 1
    browser_results = test.browser_results[0]
    assert browser_results.browser == 'chrome'
    assert len(browser_results.results) == 1
    assert browser_results.results[0].errors[0].code_frame.line == 6
    assert browser_results.results[0].errors[0].test_line == 21
