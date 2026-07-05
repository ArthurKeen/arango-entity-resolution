import { test, expect } from "@playwright/test";

test.describe("app shell smoke", () => {
  test("renders the sidebar navigation", async ({ page }) => {
    await page.goto("/");
    // Core nav items are present regardless of backend availability.
    await expect(page.getByRole("link", { name: "Data Profile" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Review" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Clusters" })).toBeVisible();
  });

  test("client-side routing updates the header title", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Data Profile" }).click();
    await expect(page).toHaveURL(/\/profile$/);
    await expect(
      page.getByRole("heading", { name: "Data Profile" }),
    ).toBeVisible();
  });

  test("theme toggle switches to dark mode", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    await expect(html).not.toHaveClass(/dark/);
    await page.getByRole("button", { name: /switch to dark mode/i }).click();
    await expect(html).toHaveClass(/dark/);
  });
});
