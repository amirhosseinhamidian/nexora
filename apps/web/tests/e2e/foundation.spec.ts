import { expect, test } from "@playwright/test";

test("Persian foundation is RTL", async ({ page }) => {
  await page.goto("/fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("زیرساخت");
});

test("English foundation is LTR", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Runtime");
});
