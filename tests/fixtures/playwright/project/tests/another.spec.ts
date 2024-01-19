import {expect, test} from '@playwright/test';

test('passing test', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', {name: 'Show'}).click();
});

test('has title will fail', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', {name: 'Show'}).click();

  await page.getByTestId('back-buttonX').click();

});

test.skip('skipped test', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', {name: 'Show'}).click();
});

test('flakey test', async ({ page }, testInfo) => {
  await page.goto('/');

  await page.route('*/**/api/stuff', async route => {
    const num= (testInfo.retry || testInfo.project.name == 'chromium')?11:10;

    const json = {num};
    await route.fulfill({json});
  });

  await page.getByRole('button', {name: 'Fetch'}).click();

  // this will fail sometimes
  await expect(page.getByTestId('num')).toContainText('11');
});
