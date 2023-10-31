import os

from cykubedrunner.builder import get_specs

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def test_get_specs_new_style():
    specs = set(get_specs(os.path.join(FIXTURE_DIR, 'new-style-cypress')))
    assert specs == {'cypress/e2e/stuff/test1.spec.ts',
                     'cypress/e2e/stuff/test2.spec.ts',
                     'cypress/e2e/nonsense/another-test.spec.ts',
                     'cypress/components/button/button.cy.ts'}


def test_get_specs_legacy_default():
    specs = set(get_specs(os.path.join(FIXTURE_DIR, 'legacy-cypress-defaults')))
    assert specs == {'cypress/integration/stuff/test1.spec.ts',
                     'cypress/integration/stuff/test2.spec.js'}


def test_get_specs_legacy_override():
    specs = set(get_specs(os.path.join(FIXTURE_DIR, 'legacy-cypress-override')))
    assert specs == {'cypress/e2e/stuff/test1.spec.ts'}


def test_default_specs():
    specs = set(get_specs(os.path.join(FIXTURE_DIR, 'nextjs')))
    assert specs == {'cypress/e2e/app.cy.ts', 'cypress/e2e/stuff/app2.cy.ts'}
