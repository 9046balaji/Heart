import { test, expect } from '@playwright/test';

test.describe('Cardio AI Assistant - End-to-End Core Flows', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to local development server
    await page.goto('http://localhost:5173');
    // Note: depending on your routing, wait for initial screen
  });

  test('should render the main application view', async ({ page }) => {
    // Verify title or main container exists
    await expect(page).toHaveTitle(/Cardio|Heart|AI/i);
    // Check if the root element that mounts react is present
    const rootElement = page.locator('#root');
    await expect(rootElement).toBeVisible();
  });

  test('should load navigation/sidebar elements', async ({ page }) => {
    // Wait for the app to hydrate fully
    await page.waitForLoadState('networkidle');

    // Basic sanity checks for UI layout
    // Assuming standard layout components exist
    const hasNav = await page.evaluate(() => {
      return document.querySelector('nav') !== null || document.querySelector('header') !== null;
    });
    expect(hasNav).toBeTruthy();
  });

});
