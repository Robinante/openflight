import { test, expect } from '@playwright/test';
import { gotoApp, KIOSK_VIEWPORTS, simulateShot, withControlSocket } from './helpers';

for (const viewport of KIOSK_VIEWPORTS) {
  test.describe(`capture readiness at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport, hasTouch: true });
    test('keeps busy and recovery visible and never leaves stale green status', async ({ page }) => {
      let state = 'waiting';
      let unavailable = false;
      await page.route('**/api/capture-status', async (route) => {
        if (unavailable) return route.abort();
        await route.fulfill({
          headers: { 'access-control-allow-origin': '*' },
          json: {
            ready: state === 'waiting',
            devices: { OPS: 'waiting', IWR: state, Camera: 'waiting' },
            raw_iwr: true,
            mock: false,
          },
        });
      });
      await withControlSocket(async (socket) => {
        await simulateShot(socket);
      });
      await gotoApp(page);
      await page.getByRole('button', { name: 'Close Select club' }).click();
      const banner = page.getByRole('status', { name: 'Capture readiness' });
      await expect(banner).toContainText('READY');
      await expect(banner).toHaveClass(/--ready/);
      expect(await banner.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
      await expect(page.locator('.live-panel__grid .metric-card')).toHaveCount(10);
      state = 'capturing';
      await expect(banner).toContainText('IWR capturing');
      await expect(banner).toHaveClass(/--busy/);
      state = 'recovering';
      await expect(banner).toContainText('IWR recovering');
      state = 'waiting';
      await expect(banner).toHaveClass(/--ready/);
      await page.screenshot({ path: `test-results/capture-ready-${viewport.width}x${viewport.height}.png` });
      unavailable = true;
      await expect(banner).toContainText('CHECKING RADARS');
      await expect(banner).not.toHaveClass(/--ready/);
    });
  });
}
