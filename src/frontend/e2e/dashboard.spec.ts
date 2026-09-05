import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("should display dashboard page title", async ({ page }) => {
    await expect(page.locator(".page-title")).toHaveText("Dashboard");
  });

  test("should display three stat cards", async ({ page }) => {
    const cards = page.locator(".stat-card");
    await expect(cards).toHaveCount(3);
  });

  test("should display stat card labels", async ({ page }) => {
    await expect(page.locator(".stat-card-label").first()).toBeVisible();
  });

  test("should have navigation sidebar", async ({ page }) => {
    await expect(page.locator(".sidebar-logo")).toHaveText("OmniCleaner");
    await expect(page.locator(".nav-item")).toHaveCount(3);
  });

  test("should navigate between pages", async ({ page }) => {
    await page.click('text=Packages');
    await expect(page.locator(".page-title")).toHaveText("Packages");

    await page.click('text=Cleaner');
    await expect(page.locator(".page-title")).toHaveText("Cleaner");

    await page.click('text=Dashboard');
    await expect(page.locator(".page-title")).toHaveText("Dashboard");
  });

  test("should have Clean Cache button", async ({ page }) => {
    const cleanButton = page.locator("button:has-text('Clean Cache')");
    await expect(cleanButton).toBeVisible();
  });
});
