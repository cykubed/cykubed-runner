import json
import os

from cykubedrunner.playwright import parse_playwright_results


def test_playwright_parse_with_failures(playwright_fixturedir):
    results = parse_playwright_results(os.path.join(playwright_fixturedir, 'playwright-results-fail.json'))

    with open(os.path.join(playwright_fixturedir, 'expected-results-fail.json')) as f:
        expected = json.dumps(json.loads(f.read()), indent=4)

    # print(results.json(indent=4))
    assert expected == results.json(indent=4)
