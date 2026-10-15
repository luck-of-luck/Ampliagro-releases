import { test, expect } from '@playwright/test';

test.describe('Onboarding', () => {
  test.skip('Fluxo Campo 60s', async ({ page }) => {
    // This test simulates a user signing up and going through the 60s onboarding flow
    await page.goto('/login/');
    await page.fill('input[name="usuario"]', 'novo_user_' + Date.now());
    await page.fill('input[name="senha"]', 'senhaforte123');
    await page.fill('input[name="email"]', 'novo_user@test.com');
    // Click register tab and submit
    await page.click('button[class="auth-btn-submit"]:has-text("Criar Conta")');

    await page.waitForURL('/onboarding/');
    await expect(page.locator('text=Bem-vindo ao Ampliagro')).toBeVisible();

    // Fill form
    await page.fill('input[name="nome_propriedade"]', 'Minha Fazenda E2E');
    await page.fill('input[name="area_total"]', '1000');
    await page.click('button[type="submit"]');

    await page.waitForURL('/dashboard/');
    await expect(page.locator('text=Minha Fazenda E2E')).toBeVisible();
  });
});
