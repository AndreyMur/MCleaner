import { test, expect } from "@playwright/test";

test.describe("Animations and motion", () => {
  test("runs a shimmer animation on loading skeletons", async ({ page }) => {
    await page.goto("/packages");

    const skeleton = page
      .locator('[data-testid="packages-skeleton"] .loading-skeleton')
      .first();
    await expect(skeleton).toBeVisible();
    await expect(skeleton).toHaveCSS("animation-name", "skeleton-loading");

    await expect(page.locator(".pkg-row")).toHaveCount(14);
    await expect(skeleton).toHaveCount(0);
  });

  test("applies a page transition when navigating between routes", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator(".page-view")).toHaveCSS("animation-name", "page-in");

    await page.locator(".nav-item", { hasText: "Packages" }).click();
    await expect(page.locator(".page-title")).toHaveText("Packages");
    await expect(page.locator(".page-view")).toHaveCSS("animation-name", "page-in");

    await page.locator(".nav-item", { hasText: "Cleaner" }).click();
    await expect(page.locator(".page-title")).toHaveText("Cleaner");
    await expect(page.locator(".page-view")).toHaveCSS("animation-name", "page-in");
  });

  test("animates modal dialog entrance", async ({ page }) => {
    await page.goto("/packages");
    await expect(page.locator(".pkg-row")).toHaveCount(14);

    const bashRow = page.locator('.pkg-row[data-package="bash"]');
    await bashRow.locator(".btn-remove").click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();
    await expect(modal).toHaveCSS("animation-name", "modal-in");
    await expect(page.locator(".modal-overlay")).toHaveCSS("animation-name", "fade-in");
  });

  test("animates toast entrance and exit", async ({ page }) => {
    await page.goto("/cleaner");
    await expect(page.getByTestId("cache-size")).toHaveText("2 GB");

    await page.getByTestId("clean-cache").click();

    const toast = page.locator(".toast-item");
    await expect(toast).toContainText("2 GB freed");
    await expect(toast).toHaveCSS("animation-name", "toast-in");

    await toast.locator(".toast-close").click();
    await expect(toast).toHaveClass(/leaving/);
    await expect(toast).toHaveCSS("animation-name", "toast-out");
    await expect(toast).toHaveCount(0);
  });

  test("disables animations when reduced motion is preferred", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/dashboard");

    await expect(page.locator(".page-view")).toHaveCSS("animation-name", "none");
  });
});
