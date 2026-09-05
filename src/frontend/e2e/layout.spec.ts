import { test, expect } from "@playwright/test";

test.describe("Responsive layout", () => {
  test("shows the full sidebar at default window size", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto("/dashboard");

    await expect(page.locator(".sidebar")).toHaveCSS("width", "248px");
    await expect(page.locator(".sidebar-brand")).toBeVisible();
    await expect(page.locator(".nav-label").first()).toBeVisible();
  });

  test("collapses the sidebar into an icon rail on narrow windows", async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 700 });
    await page.goto("/dashboard");

    await expect(page.locator(".sidebar")).toHaveCSS("width", "76px");
    await expect(page.locator(".sidebar-brand")).toBeHidden();
    await expect(page.locator(".nav-label").first()).toBeHidden();
    await expect(page.locator(".nav-icon").first()).toBeVisible();

    await page.locator(".nav-item", { hasText: "Packages" }).click();
    await expect(page.locator(".page-title")).toHaveText("Packages");
  });

  test("reflows into a top navigation bar on small screens", async ({ page }) => {
    await page.setViewportSize({ width: 600, height: 800 });
    await page.goto("/dashboard");

    await expect(page.locator(".app-layout")).toHaveCSS("flex-direction", "column");
    await expect(page.locator(".sidebar-logo")).toBeHidden();
    await expect(page.locator(".nav-label").first()).toBeVisible();

    await page.locator(".nav-item", { hasText: "Cleaner" }).click();
    await expect(page.locator(".page-title")).toHaveText("Cleaner");
  });

  test("fullscreen toggle switches the fullscreen state", async ({ page }) => {
    await page.goto("/dashboard");

    const toggle = page.getByTestId("fullscreen-toggle");
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator(".main-content")).toBeVisible();

    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");

    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
  });
});
