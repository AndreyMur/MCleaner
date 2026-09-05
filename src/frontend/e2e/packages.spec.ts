import { test, expect } from "@playwright/test";

test.describe("Package Manager", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/packages");
    await expect(page.locator(".pkg-table")).toBeVisible();
    await expect(page.locator(".pkg-row")).toHaveCount(14);
  });

  test("should display page title and package count", async ({ page }) => {
    await expect(page.locator(".page-title")).toHaveText("Packages");
    await expect(page.locator(".result-count")).toHaveText("14 packages");
  });

  test("should list packages sorted by name by default", async ({ page }) => {
    const firstRow = page.locator(".pkg-row .pkg-name").first();
    await expect(firstRow).toHaveText("bash");
  });

  test("should search packages by name", async ({ page }) => {
    await page.locator(".pkg-search").fill("vlc");
    await expect(page.locator(".pkg-row")).toHaveCount(3);
    await expect(page.locator(".result-count")).toHaveText("3 of 14");
  });

  test("should show empty state when nothing matches", async ({ page }) => {
    await page.locator(".pkg-search").fill("zzzzzz");
    await expect(page.locator(".empty-state")).toBeVisible();
    await expect(page.locator(".empty-state-title")).toHaveText("No packages found");
  });

  test("should filter packages by size", async ({ page }) => {
    await page.locator(".size-filter").selectOption({ label: "> 50 MB" });
    await expect(page.locator(".pkg-row")).toHaveCount(3);
    await expect(page.locator(".pkg-row").first()).toContainText("google-chrome-stable");

    await page.locator(".size-filter").selectOption({ label: "< 1 MB" });
    await expect(page.locator(".pkg-row")).toHaveCount(3);
  });

  test("should filter packages by install date", async ({ page }) => {
    await page.locator(".date-filter").selectOption({ label: "Last 7 days" });
    await expect(page.locator(".pkg-row")).toHaveCount(1);
    await expect(page.locator(".pkg-row")).toContainText("visual-studio-code");

    await page.locator(".date-filter").selectOption({ label: "Last 30 days" });
    await expect(page.locator(".pkg-row")).toHaveCount(2);

    await page.locator(".date-filter").selectOption({ label: "Older than 30 days" });
    await expect(page.locator(".pkg-row")).toHaveCount(12);
  });

  test("should sort packages by size", async ({ page }) => {
    await page.locator(".sort-select").selectOption({ label: "Size (largest)" });
    const firstRow = page.locator(".pkg-row .pkg-name").first();
    await expect(firstRow).toHaveText("google-chrome-stable");
  });

  test("should show dependencies and size when expanding a package", async ({ page }) => {
    const vlcRow = page.locator('.pkg-row[data-package="vlc"]');
    await vlcRow.locator(".row-toggle").click();

    const details = page.locator('[data-testid="details-vlc"]');
    await expect(details).toBeVisible();
    await expect(details.locator(".dep-chip")).toHaveCount(2);
    await expect(details.locator(".dep-chip").first()).toHaveText("libvlc5");
    await expect(details.locator(".dep-chip").nth(1)).toHaveText("vlc-plugin-video");
    await expect(details.locator(".pkg-details-value")).toHaveText(/MB/);
  });

  test("should not offer removal for auto-installed dependencies", async ({ page }) => {
    const depRow = page.locator('.pkg-row[data-package="libcurl4"]');
    await expect(depRow.locator(".btn-remove")).toHaveCount(0);
    await expect(depRow.locator(".dep-badge")).toHaveText("auto");
  });

  test("should remove package with confirmation and run autoremove", async ({ page }) => {
    await page.locator(".pkg-search").fill("vlc");
    await expect(page.locator(".pkg-row")).toHaveCount(3);

    const vlcRow = page.locator('.pkg-row[data-package="vlc"]');
    await vlcRow.locator(".btn-remove").click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("vlc");
    await expect(modal).toContainText("autoremove");
    await expect(modal).toContainText("Dependencies");
    await expect(page.locator('[data-testid="confirm-hold"]')).toContainText(
      "Safety hold"
    );

    const confirm = page.locator('[data-testid="confirm-remove"]');
    await expect(confirm).toBeDisabled();
    await expect(confirm).toBeEnabled({ timeout: 8000 });
    await confirm.click();

    await expect(modal).toHaveCount(0);
    await expect(page.locator(".operation-log")).toContainText("Autoremove cleaned 2 orphaned packages");
    await expect(page.locator(".pkg-row")).toHaveCount(0);
    await expect(page.locator(".empty-state")).toBeVisible();
  });

  test("should cancel removal when pressing cancel", async ({ page }) => {
    const bashRow = page.locator('.pkg-row[data-package="bash"]');
    await bashRow.locator(".btn-remove").click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();

    await modal.locator("button:has-text('Cancel')").click();

    await expect(modal).toHaveCount(0);
    await expect(page.locator('.pkg-row[data-package="bash"]')).toBeVisible();
    await expect(page.locator(".pkg-row")).toHaveCount(14);
  });
});
