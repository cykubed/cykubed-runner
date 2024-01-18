import json
import os

from cykubedrunner.common.schemas import NewTestRun
from cykubedrunner.cypress import CypressSpecRunner
from cykubedrunner.settings import settings


def test_cypress_parse_fail_inside_helper(mocker, testrun: NewTestRun, cypress_fixturedir):
    """
    If the test fails inside a helper function then record the original line number
    """
    jsonfile = os.path.join(cypress_fixturedir, 'fail-inside-helper/out.json')
    os.makedirs(os.path.join(settings.src_dir, 'node_modules'))
    os.makedirs(os.path.join(settings.BUILD_DIR, 'cypress_cache'))

    runner = CypressSpecRunner(None, testrun, 'cypress/e2e/stuff/test1.spec.ts',
                               'chrome')

    runner.results_file = jsonfile
    result = runner.parse_results()

    with open(os.path.join(cypress_fixturedir, 'fail-inside-helper/expected.json')) as f:
        expected = json.dumps(json.loads(f.read()), indent=4)

    # print(results.json(indent=4))
    assert expected == result.json(indent=4)
