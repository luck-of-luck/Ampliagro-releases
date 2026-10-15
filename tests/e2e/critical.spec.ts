import { test, expect } from '@playwright/test';

test.describe('Critical User Flows', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/accounts/login/');
    await page.fill('input[name="login"]', 'teste');
    await page.fill('input[name="password"]', 'teste123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/');
  });

  test('Login and access dashboard', async ({ page }) => {
    await expect(page).toHaveTitle(/Ampliagro/);
    await expect(page.locator('text=Dashboard')).toBeVisible();
  });

  test('Create property onboarding', async ({ page }) => {
    await page.goto('/onboarding/');
    await page.fill('input[name="nome_fazenda"]', 'Fazenda Teste E2E');
    await page.fill('input[name="area"]', '100');
    await page.selectOption('select[name="uf"]', 'MT');
    await page.fill('input[name="cidade"]', 'Primavera do Leste');
    await page.click('button[type="submit"]');
    await expect(page.locator('text=Propriedade criada')).toBeVisible();
  });

  test('Create talhão with geometry', async ({ page }) => {
    await page.goto('/cadastro/talhao/');
    await page.fill('input[name="nome"]', 'Talhão E2E');
    await page.fill('input[name="area_hectare"]', '50');
    await page.selectOption('select[name="cultura_atual"]', 'Soja');
    // Draw polygon on map (simplified)
    await page.click('button:has-text("Desenhar")');
    await page.waitForTimeout(500);
    await page.click('button:has-text("Salvar")');
    await expect(page.locator('text=Talhão salvo')).toBeVisible();
  });

  test('Create safra with multiple talhões', async ({ page }) => {
    await page.goto('/cadastro/safra/');
    await page.fill('input[name="safra_nome"]', 'Safra 2024/25');
    await page.selectOption('select[name="cultura"]', 'Soja');
    await page.fill('input[name="ano"]', '2024');
    await page.fill('input[name="area_plantada"]', '200');
    await page.click('button:has-text("Salvar")');
    await expect(page.locator('text=Safra criada')).toBeVisible();
  });

  test('Create presets and widgets', async ({ page }) => {
    await page.goto('/');
    await page.click('button:has-text("Adicionar Widget")');
    await page.click('button:has-text("Linha")');
    await page.click('button:has-text("Suave")');
    await page.click('button:has-text("Inserir")');
    await expect(page.locator('text=Widget adicionado')).toBeVisible();
  });

  test('Market data loads for Soja', async ({ page }) => {
    await page.goto('/');
    await page.click('button:has-text("Adicionar Widget")');
    await page.click('button:has-text("Vegetal")');
    await page.click('button:has-text("Soja")');
    await page.click('button:has-text("Mercado")');
    await expect(page.locator('text=Valor da Saca')).toBeVisible();
    await expect(page.locator('text=Produção Total')).toBeVisible();
  });

  test('Bank conciliation flow', async ({ page }) => {
    await page.goto('/financeiro/conciliacao/');
    await page.click('button:has-text("Nova Conciliação")');
    await page.selectOption('select[name="conta"]', 'Banco do Brasil');
    await page.fill('input[name="data_inicio"]', '2024-01-01');
    await page.fill('input[name="data_fim"]', '2024-01-31');
    await page.fill('input[name="saldo_sistema_fim"]', '50000');
    await page.fill('input[name="saldo_banco_fim"]', '50000');
    await page.click('button:has-text("Fechar")');
    await expect(page.locator('text=Conciliado')).toBeVisible();
  });

  test('NF-e import', async ({ page }) => {
    await page.goto('/financeiro/nfe/');
    await page.setInputFiles('input[name="xml"]', 'tests/fixtures/nfe_sample.xml');
    await page.click('button:has-text("Importar")');
    await expect(page.locator('text=Importado')).toBeVisible();
  });

  test('QR code generation', async ({ page }) => {
    await page.goto('/rastreabilidade/');
    await page.click('button:has-text("Gerar QR")');
    await page.fill('input[name="lote_id"]', 'LOTE-001');
    await page.click('button:has-text("Gerar")');
    await expect(page.locator('canvas')).toBeVisible();
  });

  test('Offline capability', async ({ page, context }) => {
    await page.goto('/');
    await context.setOffline(true);
    await page.goto('/cadastro/safra/');
    await page.fill('input[name="safra_nome"]', 'Safra Offline');
    await page.click('button:has-text("Salvar")');
    await expect(page.locator('text=Salvo localmente')).toBeVisible();
    await context.setOffline(false);
    await page.waitForTimeout(2000);
    await expect(page.locator('text=Sincronizado')).toBeVisible();
  });
});