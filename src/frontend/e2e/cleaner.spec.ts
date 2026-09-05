import { test, expect } from "@playwright/test";

test.describe("Cleaner Module", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/cleaner");
    await expect(page.locator('[data-testid="cache-card"]')).toBeVisible();
    await expect(page.locator('[data-testid="cache-size"]')).toHaveText("2 GB");
    await expect(page.locator('[data-testid="orphans-list"] .orphan-row')).toHaveCount(4);
  });

  test("should display page title and subtitle", async ({ page }) => {
    await expect(page.locator(".page-title")).toHaveText("Cleaner");
    await expect(page.locator(".page-subtitle")).toContainText("Clean system junk");
  });

  test("should show cache size and clean cache button", async ({ page }) => {
    const cacheCard = page.locator('[data-testid="cache-card"]');
    await expect(cacheCard.locator(".cleaner-card-title")).toHaveText("Package cache");
    await expect(cacheCard.locator('[data-testid="clean-cache"]')).toBeEnabled();
  });

  test("should clean cache with progress bar and success toast", async ({ page }) => {
    await page.locator('[data-testid="clean-cache"]').click();

    await expect(page.locator('[data-testid="clean-progress"]')).toBeVisible();
    await expect(page.locator('[data-testid="clean-cache"]')).toBeDisabled();

    const toast = page.locator(".toast-item.toast-success");
    await expect(toast).toBeVisible();
    await expect(toast).toContainText("2 GB freed");

    await expect(page.locator('[data-testid="clean-progress"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="cache-size"]')).toHaveText("0 B");
    await expect(page.locator('[data-testid="clean-cache"]')).toBeDisabled();
  });

  test("should list orphaned packages with reclaimable size", async ({ page }) => {
    const orphansCard = page.locator('[data-testid="orphans-card"]');
    await expect(orphansCard.locator(".cleaner-card-title")).toHaveText("Orphaned packages");
    await expect(orphansCard.locator('[data-testid="orphans-summary"]')).toHaveText("4 packages");
    await expect(orphansCard.locator('[data-testid="orphans-size"]')).toHaveText("19.65 MB reclaimable");

    const firstRow = page.locator('[data-testid="orphans-list"] .orphan-row').first();
    await expect(firstRow.locator(".orphan-name")).toHaveText("libvlc5");

    await expect(page.locator('[data-testid="remove-orphans"]')).toHaveText("Remove orphans (4)");
  });

  test("should show dry-run summary before removing orphans", async ({ page }) => {
    await page.locator('[data-testid="remove-orphans"]').click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();
    await expect(modal.locator(".modal-title")).toHaveText("Remove orphaned packages");
    await expect(modal.locator('[data-testid="modal-orphan-list"] .orphan-row')).toHaveCount(4);
    await expect(modal).toContainText("apt autoremove");
    await expect(modal.locator(".modal-fact-value").first()).toHaveText("4");
  });

  test("should remove orphans with confirmation", async ({ page }) => {
    await page.locator('[data-testid="remove-orphans"]').click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();
    await page.locator('[data-testid="confirm-orphans-removal"]').click();

    await expect(modal).toHaveCount(0);

    const toast = page.locator(".toast-item.toast-success");
    await expect(toast).toBeVisible();
    await expect(toast).toContainText("orphaned packages removed");

    await expect(page.locator('[data-testid="orphans-list"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="orphans-empty"]')).toBeVisible();
    await expect(page.locator('[data-testid="orphans-summary"]')).toHaveText("0 packages");
    await expect(page.locator('[data-testid="remove-orphans"]')).toBeDisabled();
  });

  test("should cancel orphan removal and keep packages", async ({ page }) => {
    await page.locator('[data-testid="remove-orphans"]').click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();
    await modal.locator("button:has-text('Cancel')").click();

    await expect(modal).toHaveCount(0);
    await expect(page.locator('[data-testid="orphans-list"] .orphan-row')).toHaveCount(4);
    await expect(page.locator('[data-testid="orphans-summary"]')).toHaveText("4 packages");
  });

  test("should stream operations to the journal panel", async ({ page }) => {
    const log = page.locator('[data-testid="journal-log"]');
    await expect(log).toContainText("Operations will be shown here.");

    await page.locator('[data-testid="clean-cache"]').click();
    await expect(log).toContainText("$ apt clean");
    await expect(log).toContainText("Cache cleaned");

    await page.locator(".journal-clear").click();
    await expect(log).toContainText("Operations will be shown here.");
  });
});
