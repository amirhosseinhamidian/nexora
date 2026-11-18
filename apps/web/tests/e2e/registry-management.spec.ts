import { expect, type Locator, type Page, test } from "@playwright/test";

type Row = Record<string, unknown> & { name: string; row_version: number; status: string };
type Write = { path: string; body: Record<string, unknown> };

async function mockRegistry(page: Page) {
  const rows: Record<"assets" | "portfolios" | "accounts", Row[]> = {
    assets: [
      {
        asset_id: "usd",
        asset_key: "usd",
        asset_class: "fiat",
        name: "US Dollar",
        symbol: "USD",
        precision: 2,
        status: "active",
        row_version: 3,
      },
    ],
    portfolios: [
      {
        portfolio_id: "portfolio-1",
        portfolio_key: "core-portfolio",
        base_asset_id: "usd",
        kind: "personal",
        name: "Core portfolio",
        status: "active",
        row_version: 1,
      },
    ],
    accounts: [],
  };
  const writes: Write[] = [];
  const state = { loseAssetResponse: false, conflictOnce: false };
  const terminal = { assets: "inactive", portfolios: "archived", accounts: "closed" };
  const idKeys = { assets: "asset_id", portfolios: "portfolio_id", accounts: "account_id" };
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({ json: { owner_id: "owner-1", recently_reauthenticated: false } }),
  );
  await page.route("**/api/health/ready", (route) => route.fulfill({ json: { status: "ready" } }));
  for (const resource of ["assets", "portfolios", "accounts"] as const) {
    const path = `/api/v1/${resource}`;
    const items = rows[resource];
    await page.route(`**${path}`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: { items } });
        return;
      }
      const body = route.request().postDataJSON() as Record<string, unknown>;
      writes.push({ path, body });
      const record = {
        ...body,
        [idKeys[resource]]: `${resource}-${items.length + 1}`,
        name: String(body.name),
        status: "active",
        row_version: 1,
      };
      items.push(record);
      if (resource === "assets" && state.loseAssetResponse) {
        state.loseAssetResponse = false;
        await route.abort();
        return;
      }
      await route.fulfill({ status: 201, json: record });
    });
    await page.route(`**${path}/*/*`, async (route) => {
      const requestPath = new URL(route.request().url()).pathname;
      const body = route.request().postDataJSON() as Record<string, unknown>;
      writes.push({ path: requestPath, body });
      const [, id, action] = requestPath.slice(path.length).split("/");
      if (action === "identifiers") {
        await route.fulfill({ status: 201, json: { asset_id: id, ...body } });
        return;
      }
      const record = items.find((item) => item[idKeys[resource]] === id);
      if (!record) {
        await route.fulfill({ status: 404, json: { error: { code: "REGISTRY_NOT_FOUND" } } });
        return;
      }
      record.status = terminal[resource];
      record.row_version += 1;
      if (state.conflictOnce) {
        state.conflictOnce = false;
        await route.fulfill({ status: 409, json: { error: { code: "REGISTRY_STATE_CONFLICT" } } });
        return;
      }
      await route.fulfill({ json: record });
    });
  }
  return { rows, state, writes };
}

async function choose(dialog: Locator, page: Page, field: string, value: string) {
  await dialog.getByRole("combobox", { name: field, exact: true }).click();
  await page
    .getByRole("listbox", { name: field, exact: true })
    .getByRole("option", { name: value, exact: true })
    .click();
}

test("manages assets, portfolios and accounts with explicit lifecycle confirmation", async ({
  page,
}) => {
  const runtime = await mockRegistry(page);
  runtime.state.loseAssetResponse = true;
  await page.goto("/en/assets");

  await page.getByRole("button", { name: "Register asset" }).click();
  const createAsset = page.getByRole("dialog", { name: "Register asset" });
  await createAsset.getByLabel("Name", { exact: true }).fill("British Pound");
  await createAsset.getByLabel("Asset symbol").fill("gbp");
  await createAsset.getByRole("button", { name: "Register asset" }).click();
  const asset = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "British Pound" }) });
  await expect(asset).toContainText("GBP");
  expect(runtime.writes).toHaveLength(1);
  expect(runtime.writes[0]).toMatchObject({
    path: "/api/v1/assets",
    body: { name: "British Pound", symbol: "GBP", asset_class: "fiat", precision: 2 },
  });

  await asset.getByRole("button", { name: "Add identifier" }).click();
  const identifier = page.getByRole("dialog", { name: "Add identifier" });
  await choose(identifier, page, "Identifier type", "Currency code (ISO 4217)");
  await identifier.getByRole("textbox", { name: "Identifier", exact: true }).fill("GBP");
  await identifier.getByRole("checkbox", { name: "Primary identifier" }).check();
  await identifier.getByRole("button", { name: "Add identifier" }).click();
  await expect(page.getByText("Identifier added.")).toBeVisible();
  expect(runtime.writes[1]).toEqual({
    path: "/api/v1/assets/assets-2/identifiers",
    body: { scheme: "iso_4217", value: "GBP", is_primary: true },
  });

  const navigation = page.getByRole("navigation", { name: "Workspace navigation" });
  await navigation.getByRole("link", { name: "Portfolios", exact: true }).click();
  await page.getByRole("button", { name: "Create portfolio" }).click();
  const createPortfolio = page.getByRole("dialog", { name: "Create portfolio" });
  await createPortfolio.getByLabel("Name", { exact: true }).fill("Travel fund");
  await choose(createPortfolio, page, "Base asset", "British Pound (GBP)");
  await createPortfolio.getByRole("button", { name: "Create portfolio" }).click();
  const portfolio = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "Travel fund" }) });
  await expect(portfolio).toContainText("British Pound (GBP)");
  expect(runtime.writes[2]).toMatchObject({
    path: "/api/v1/portfolios",
    body: { name: "Travel fund", base_asset_id: "assets-2", kind: "personal" },
  });

  await navigation.getByRole("link", { name: "Accounts", exact: true }).click();
  await page.getByRole("button", { name: "Add account" }).click();
  const createAccount = page.getByRole("dialog", { name: "Add account" });
  await createAccount.getByLabel("Name", { exact: true }).fill("Cash wallet");
  await choose(createAccount, page, "Portfolio", "Travel fund");
  await createAccount.getByLabel("Institution name").fill("Home");
  await createAccount.getByRole("button", { name: "Add account" }).click();
  const account = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "Cash wallet" }) });
  await expect(account).toContainText("Home");
  expect(runtime.writes[3]).toMatchObject({
    path: "/api/v1/accounts",
    body: {
      name: "Cash wallet",
      portfolio_id: "portfolios-2",
      institution_name: "Home",
      kind: "cash",
    },
  });

  await account.getByRole("button", { name: "Close account" }).click();
  const close = page.getByRole("dialog", { name: "Close this account?" });
  await expect(close).toContainText("Cash wallet");
  await page.keyboard.press("Escape");
  await expect(close).toHaveCount(0);
  expect(runtime.writes).toHaveLength(4);
  await account.getByRole("button", { name: "Close account" }).click();
  await close.getByRole("button", { name: "Close account", exact: true }).click();
  await expect(account.getByText("Closed", { exact: true })).toBeVisible();

  await navigation.getByRole("link", { name: "Portfolios", exact: true }).click();
  await portfolio.getByRole("button", { name: "Archive portfolio" }).click();
  await page
    .getByRole("dialog", { name: "Archive this portfolio?" })
    .getByRole("button", { name: "Archive portfolio", exact: true })
    .click();
  await expect(portfolio.getByText("Archived", { exact: true })).toBeVisible();
  await expect(portfolio.getByRole("link", { name: "View portfolio details" })).toBeVisible();

  await navigation.getByRole("link", { name: "Assets", exact: true }).click();
  await asset.getByRole("button", { name: "Deactivate asset" }).click();
  await page
    .getByRole("dialog", { name: "Deactivate this asset?" })
    .getByRole("button", { name: "Deactivate asset", exact: true })
    .click();
  await expect(asset.getByText("Inactive", { exact: true })).toBeVisible();
  expect(runtime.writes.slice(4)).toEqual([
    { path: "/api/v1/accounts/accounts-1/close", body: { expected_row_version: 1 } },
    { path: "/api/v1/portfolios/portfolios-2/archive", body: { expected_row_version: 1 } },
    { path: "/api/v1/assets/assets-2/deactivate", body: { expected_row_version: 1 } },
  ]);
});

test("refreshes a changed record after a version conflict on a Persian mobile page", async ({
  page,
}) => {
  const runtime = await mockRegistry(page);
  runtime.state.conflictOnce = true;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/fa/assets");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  const registry = page.getByRole("region", { name: "دارایی‌های ثبت‌شده" });
  await registry.getByRole("searchbox", { name: "جست‌وجو" }).fill("usd");
  await registry.getByRole("button", { name: "غیرفعال کردن دارایی" }).click();
  await page
    .getByRole("dialog", { name: "این دارایی غیرفعال شود؟" })
    .getByRole("button", { name: "غیرفعال کردن دارایی", exact: true })
    .click();
  const notifications = registry.getByRole("region", { name: "اعلان‌های فهرست ثبت‌شده‌ها" });
  await expect(notifications.getByRole("status")).toContainText("این رکورد تغییر کرده");
  await expect(registry.getByText("غیرفعال", { exact: true })).toBeVisible();
  await expect(registry.getByRole("button", { name: "غیرفعال کردن دارایی" })).toHaveCount(0);
  expect(runtime.writes).toEqual([
    { path: "/api/v1/assets/usd/deactivate", body: { expected_row_version: 3 } },
  ]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

test("guides an empty registry to first-run setup", async ({ page }) => {
  const runtime = await mockRegistry(page);
  runtime.rows.portfolios.length = 0;
  await page.goto("/en/accounts");
  await page.getByRole("link", { name: "Open portfolios", exact: true }).click();
  await expect(page).toHaveURL("/en/portfolios");
  await expect(page.getByRole("button", { name: "Create portfolio", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Create your first portfolio", exact: true }).click();
  await expect(page).toHaveURL("/en/onboarding");
  expect(runtime.writes).toEqual([]);
});
