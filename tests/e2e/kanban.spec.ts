import { test, expect } from '@playwright/test';

test.describe('Kanban do Operário', () => {
  test.beforeEach(async ({ page }) => {
    // Fazer login como operário/servidor
    await page.goto('/login/');
    await page.click('#btnServidor');
    await page.fill('#inputFazenda', 'Fazenda Modelo - Primavera do Leste');
    await page.fill('input[name="usuario"]', 'mecanico.demo');
    await page.fill('input[name="senha"]', 'mec123');
    await page.click('#btnEntrar');
    await page.waitForURL(/servidor|\/dashboard/);
  });

  test('lista tarefas no painel do operário', async ({ page }) => {
    // Ajustar rota se necessário, ex: /operario/
    // Clica no link do Kanban, caso exista na navbar, ou acessa diretamente
    await page.goto('/servidor/kanban/');

    // Verifica se as colunas do Kanban (Pendente, Andamento, Concluído) estão visíveis
    await expect(page.locator('.kanban-column').first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Pendente', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Em Andamento', exact: true })).toBeVisible();
  });
});
