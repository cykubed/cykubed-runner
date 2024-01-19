import os

from cykubedrunner.builder import get_cypress_specs


def test_get_specs_new_style(cypress_fixturedir):
    specs = set(get_cypress_specs(os.path.join(cypress_fixturedir, 'new-style-cypress')))
    assert specs == {'cypress/e2e/stuff/test1.spec.ts',
                     'cypress/e2e/stuff/test2.spec.ts',
                     'cypress/e2e/nonsense/another-test.spec.ts',
                     'cypress/components/button/button.cy.ts'}


def test_get_specs_legacy_default(cypress_fixturedir):
    specs = set(get_cypress_specs(os.path.join(cypress_fixturedir, 'legacy-cypress-defaults')))
    assert specs == {'cypress/integration/stuff/test1.spec.ts',
                     'cypress/integration/stuff/test2.spec.js'}


def test_get_specs_legacy_override(cypress_fixturedir):
    specs = set(get_cypress_specs(os.path.join(cypress_fixturedir, 'legacy-cypress-override')))
    assert specs == {'cypress/e2e/stuff/test1.spec.ts'}


def test_default_specs(cypress_fixturedir):
    specs = set(get_cypress_specs(os.path.join(cypress_fixturedir, 'nextjs')))
    assert specs == {'cypress/e2e/app.cy.ts', 'cypress/e2e/stuff/app2.cy.ts'}
