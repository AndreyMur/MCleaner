import { test, expect } from "@playwright/test";

const ELEVATED = "omnicleaner.mock.elevated";
const SLOW = "omnicleaner.mock.slow";

test.describe("Safety", () => {
  test("shows the elevation banner and requests admin rights", async ({ page }) => {
    await page.addInitScript(([key]) => {
      window.localStorage.setItem(key, "0");
    }, [ELEVATED]);

    await page.goto("/cleaner");
    await expect(page.getByTestId("cache-card")).toBeVisible();

    const banner = page.getByTestId("privilege-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("administrator rights");

    await page.getByTestId("request-elevation").click();
    await expect(page.getByTestId("privilege-banner")).toHaveCount(0);
  });

  test("seamlessly requests elevation before a bulk removal", async ({ page }) => {
    await page.addInitScript(([key]) => {
      window.localStorage.setItem(key, "0");
    }, [ELEVATED]);

    await page.goto("/cleaner");
    await expect(page.getByTestId("orphans-list").locator(".orphan-row")).toHaveCount(4);

    await page.getByTestId("remove-orphans").click();
    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();

    const confirm = page.getByTestId("confirm-orphans-removal");
    await expect(confirm).toBeEnabled({ timeout: 8000 });
    await confirm.click();

    await expect(page.getByTestId("privilege-banner")).toHaveCount(0);
    const toast = page.locator(".toast-item.toast-success");
    await expect(toast).toBeVisible();
    await expect(toast).toContainText("orphaned packages removed");
  });

  test("records a recovery point before removing orphaned packages", async ({ page }) => {
    await page.goto("/cleaner");
    await expect(page.getByTestId("orphans-list").locator(".orphan-row")).toHaveCount(4);

    await page.getByTestId("remove-orphans").click();
    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();

    const recoveryNote = modal.getByTestId("modal-recovery");
    await expect(recoveryNote).toBeVisible();
    await expect(recoveryNote).toContainText("Timeshift");
    await expect(recoveryNote).toContainText("snapshot");

    const confirm = page.getByTestId("confirm-orphans-removal");
    await expect(confirm).toBeEnabled({ timeout: 8000 });
    await confirm.click();

    const log = page.getByTestId("journal-log");
    await expect(log).toContainText("Recovery point created");
    await expect(log).toContainText("Removed 4 orphaned packages");

    const toast = page.locator(".toast-item.toast-success");
    await expect(toast).toContainText("orphaned packages removed");
  });

  test("aborts a long operation without clearing the cache", async ({ page }) => {
    await page.addInitScript(([key]) => {
      window.localStorage.setItem(key, "40");
    }, [SLOW]);

    await page.goto("/cleaner");
    await expect(page.getByTestId("cache-card")).toBeVisible();
    await expect(page.getByTestId("cache-size")).toHaveText("2 GB");

    await page.getByTestId("clean-cache").click();
    await expect(page.getByTestId("clean-progress")).toBeVisible();
    await expect(page.getByTestId("abort-cache-clean")).toBeVisible();

    await page.getByTestId("abort-cache-clean").click();

    const toast = page.locator(".toast-item.toast-info");
    await expect(toast).toBeVisible();
    await expect(toast).toContainText("Cache clean aborted");

    await expect(page.getByTestId("clean-progress")).toHaveCount(0);
    await expect(page.getByTestId("cache-size")).toHaveText("2 GB");
    await expect(page.getByTestId("clean-cache")).toBeEnabled();
  });
});
