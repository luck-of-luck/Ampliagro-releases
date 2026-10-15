import { test, expect } from '@playwright/test';

test('login produtor', async ({ page }) => {
  await page.goto('/login/');
  await page.fill('input[name="usuario"]', 'demo');
  await page.fill('input[name="senha"]', 'demo123');
  await page.click('#btnEntrar');
  await expect(page).toHaveURL(/dashboard|\/$/);
});

test('login falha com senha errada', async ({ page }) => {
  await page.goto('/login/');
  await page.fill('input[name="usuario"]', 'demo');
  await page.fill('input[name="senha"]', 'errada');
  await page.click('#btnEntrar');
  await expect(page.locator('.auth-error, .error, .alert, .bg-red-50, .text-red-500').first()).toBeVisible();
});
