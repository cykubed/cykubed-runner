import {expect, test} from '@playwright/test';

test('this will be ignored', async ({ page }) => {
  await page.goto('http://localhost:4200');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Dummyui/);

  await page.getByRole('button', {name: 'Show'}).click();

  await page.getByTestId('next');
});
