import json
import os

from cykubedrunner.cypress import parse_cypress_results


def test_cypress_parse_fail_inside_helper(mocker, cypress_fixturedir):
    """
    If the test fails inside a helper function then record the original line number
    """
    mocker.patch('cykubedrunner.settings.RunnerSettings.get_results_dir',
                 return_value=os.path.join(cypress_fixturedir, 'fail-inside-helper'))

    jsonfile = os.path.join(cypress_fixturedir, 'fail-inside-helper/out.json')

    result = parse_cypress_results(jsonfile, 'chrome',
                                    'cypress/e2e/stuff/test1.spec.ts')

    with open(os.path.join(cypress_fixturedir, 'fail-inside-helper/expected.json')) as f:
        expected = json.dumps(json.loads(f.read()), indent=4)

    # print(results.json(indent=4))
    assert expected == result.json(indent=4)
