import { expect, test } from "@playwright/test";

async function mockPrivateRuntime(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        owner_id: "113f777b-f75b-46e5-91da-91d9601c03ea",
        recently_reauthenticated: true,
        rotation_required: false,
        schema_version: "nexora-runtime-api-v1",
      },
    }),
  );
  await page.route("**/api/health/ready", (route) =>
    route.fulfill({ contentType: "application/json", json: { status: "ready" } }),
  );
  await page.route("**/api/v1/portfolios", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [
          {
            base_asset_id: "asset-usd",
            kind: "personal",
            name: "Core portfolio",
            portfolio_id: "portfolio-1",
            portfolio_key: "core-portfolio",
            status: "active",
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/accounts", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [
          {
            account_id: "account-1",
            account_key: "private-broker",
            institution_name: "Private Broker",
            kind: "brokerage_manual",
            name: "Brokerage",
            portfolio_id: "portfolio-1",
            status: "active",
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/assets", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [
          { asset_id: "asset-usd", name: "US Dollar", status: "active", symbol: "USD" },
          { asset_id: "asset-btc", name: "Bitcoin", status: "active", symbol: "BTC" },
        ],
      },
    }),
  );
  await page.route("**/api/v1/portfolios/portfolio-1/analytics?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        as_of: "2026-11-03T12:00:00Z",
        nav: "12500",
        positions: [{ asset_id: "asset-btc", market_value: "12500", state: "fresh" }],
        priced_value: "12500",
        realized_pnl: "120",
        state: "complete",
        unrealized_pnl: "450",
      },
    }),
  );
  await page.route("**/api/v1/portfolios/portfolio-1/valuation-status?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: { as_of: "2026-11-03T12:00:00Z", items: [{ asset_id: "asset-btc", state: "fresh" }] },
    }),
  );
}

test("Persian authenticated shell is RTL and responsive", async ({ page }) => {
  await mockPrivateRuntime(page);
  await page.goto("/fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("داشبورد پورتفولیو");
  await expect(page.locator(".ready-badge")).toHaveText("نشست مالک فعال است");
  await expect(page.getByRole("heading", { name: "نمای کلی پورتفولیو" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "دفتر حساب‌ها" })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("navigation")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brokerage" })).toBeVisible();
});

test("English login exposes a passkey-only flow", async ({ page }) => {
  await page.goto("/en/login");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Continue with your passkey");
  await expect(page.getByRole("button", { name: "Sign in with passkey" })).toBeVisible();
  await expect(page.getByLabel("Password")).toHaveCount(0);
});

test("expired session presents a bounded recovery action", async ({ page }) => {
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        correlation_id: "d7d23916-e3d5-41ee-932e-1f1ae08c1825",
        error: { code: "AUTHENTICATION_DENIED", message: "request denied" },
        schema_version: "nexora-error-envelope-v1",
      },
      status: 401,
    }),
  );
  await page.goto("/en");
  await expect(page.getByRole("heading", { name: "Session expired" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Go to sign in" })).toHaveAttribute(
    "href",
    "/en/login",
  );
});
