import { expect, type Page, test } from "@playwright/test";

const assetId = "81f3cce1-a58d-43fa-aa90-a2ebbf9ca38d";
const portfolioId = "815c0d99-e74b-451f-8051-f11a7e37c855";
const accountId = "7db169eb-b9ce-4379-804b-e356a735395a";
const dollar = {
  asset_class: "fiat",
  asset_id: assetId,
  asset_key: "usd",
  name: "US Dollar",
  precision: 2,
  status: "active",
  symbol: "USD",
};

async function mockRegistry(page: Page, assets: Record<string, unknown>[] = []) {
  const portfolios: Record<string, unknown>[] = [];
  const accounts: Record<string, unknown>[] = [];
  const writes: string[] = [];
  const state = {
    expirePortfolioOnce: false,
    sessionExpired: false,
    loseAccountResponse: false,
    failAccountLookup: false,
    conflictAccountOnce: false,
  };
  const expired = {
    error: { code: "AUTHENTICATION_DENIED", message: "request denied" },
  };
  await page.route("**/api/v1/auth/session", (route) =>
    state.sessionExpired
      ? route.fulfill({ status: 401, json: expired })
      : route.fulfill({ json: { owner_id: "owner-1", recently_reauthenticated: true } }),
  );
  await page.route("**/api/health/ready", (route) => route.fulfill({ json: { status: "ready" } }));

  const resources = [
    { endpoint: "assets", items: assets, idKey: "asset_id", id: assetId },
    { endpoint: "portfolios", items: portfolios, idKey: "portfolio_id", id: portfolioId },
    { endpoint: "accounts", items: accounts, idKey: "account_id", id: accountId },
  ];
  for (const { endpoint, items, idKey, id } of resources) {
    await page.route(`**/api/v1/${endpoint}`, async (route) => {
      if (route.request().method() === "GET") {
        if (endpoint === "accounts" && state.failAccountLookup) {
          state.failAccountLookup = false;
          await route.abort();
          return;
        }
        await route.fulfill({ json: { items } });
        return;
      }
      writes.push(endpoint);
      if (endpoint === "portfolios" && state.expirePortfolioOnce) {
        state.expirePortfolioOnce = false;
        state.sessionExpired = true;
        await route.fulfill({ status: 401, json: expired });
        return;
      }
      const record = { ...route.request().postDataJSON(), [idKey]: id, status: "active" };
      if (endpoint === "accounts" && state.conflictAccountOnce) {
        state.conflictAccountOnce = false;
        items.push({ ...record, name: "Different account" });
        await route.fulfill({
          status: 409,
          json: { error: { code: "REGISTRY_STATE_CONFLICT", message: "request denied" } },
        });
        return;
      }
      items.push(record);
      if (endpoint === "accounts" && state.loseAccountResponse) {
        state.loseAccountResponse = false;
        state.failAccountLookup = true;
        await route.abort();
        return;
      }
      await route.fulfill({ status: 201, json: record });
    });
  }
  return { accounts, assets, portfolios, state, writes };
}

test("creates a first portfolio and recovers a saved account after a lost response", async ({
  page,
}) => {
  const runtime = await mockRegistry(page);
  runtime.state.loseAccountResponse = true;
  await page.goto("/en/overview");
  await page.getByRole("link", { name: "Create your first portfolio" }).click();
  await expect(page).toHaveURL("/en/onboarding");

  await page.getByLabel("Asset name").fill("US Dollar");
  await page.getByLabel("Asset symbol").fill("USD");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Portfolio name").fill("My first portfolio");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("checkbox", { name: "Add an account now" }).check();
  await page.getByLabel("Account name").fill("Cash wallet");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Cash wallet · Cash")).toBeVisible();
  expect(runtime.writes).toEqual([]);

  await page.getByRole("button", { name: "Review and save" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Save setup" }).click();
  const review = page.getByRole("region", { name: "Review", exact: true });
  await expect(review.getByRole("alert")).toContainText(
    "The last operation could not be confirmed",
  );
  expect(runtime.writes).toEqual(["assets", "portfolios", "accounts"]);

  await page.reload();
  await expect(page.getByText("Cash wallet · Cash")).toBeVisible();
  await page.getByRole("button", { name: "Try again" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Save setup" }).click();
  await expect(page.getByRole("heading", { name: "Your portfolio is ready" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open portfolio" })).toHaveAttribute(
    "href",
    `/en/portfolios/${portfolioId}`,
  );
  expect(runtime.writes).toEqual(["assets", "portfolios", "accounts"]);
  expect(runtime.portfolios[0]?.base_asset_id).toBe(assetId);
  expect(runtime.accounts[0]?.portfolio_id).toBe(portfolioId);
  await page.goto("/en/onboarding");
  await expect(page.getByRole("heading", { name: "You already have a portfolio" })).toBeVisible();
});

test("preserves setup after session expiry and supports an existing asset without an account", async ({
  page,
}) => {
  const runtime = await mockRegistry(page, [
    {
      ...dollar,
      asset_id: "3eaba516-3083-4e5d-b601-fd48907822c7",
      asset_key: "eur",
      name: "Euro",
      symbol: "EUR",
    },
    dollar,
  ]);
  runtime.state.expirePortfolioOnce = true;
  await page.goto("/fa/onboarding");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  const assetStep = page.getByRole("region", { name: "دارایی پایه", exact: true });
  const assetSelector = assetStep.getByRole("combobox", { name: "دارایی پایه", exact: true });
  await expect(assetSelector).toContainText("Euro (EUR)");
  await assetSelector.click();
  const options = assetStep.getByRole("listbox", { name: "دارایی پایه", exact: true });
  await expect(options).toBeVisible();
  await expect(options).toHaveCSS("direction", "rtl");
  await options.getByRole("option", { name: "US Dollar (USD)" }).click();
  await expect(assetSelector).toContainText("US Dollar (USD)");
  await page.getByRole("button", { name: "ادامه", exact: true }).click();
  await page.getByLabel("نام پرتفوی").fill("پرتفوی شخصی من");
  await page.getByRole("button", { name: "ادامه", exact: true }).click();
  await page.getByRole("button", { name: "ادامه", exact: true }).click();
  await page.getByRole("button", { name: "مرور و ثبت" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "ثبت اطلاعات" }).click();
  await expect(page.locator('a[href="/fa/login?resume=onboarding"]')).toBeVisible();

  runtime.state.sessionExpired = false;
  await page.goto("/fa/onboarding");
  await expect(page.getByText("پرتفوی شخصی من · شخصی")).toBeVisible();
  await page.getByRole("button", { name: "تلاش دوباره" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "ثبت اطلاعات" }).click();
  await expect(page.getByRole("heading", { name: "پرتفوی شما آماده است" })).toBeVisible();
  expect(runtime.portfolios).toHaveLength(1);
  expect(runtime.portfolios[0]?.base_asset_id).toBe(assetId);
  expect(runtime.writes).toEqual(["portfolios", "portfolios"]);
});

test("lets the owner skip an optional account after a conflict without recreating the portfolio", async ({
  page,
}) => {
  const runtime = await mockRegistry(page, [dollar]);
  runtime.state.conflictAccountOnce = true;
  await page.goto("/en/onboarding");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Portfolio name").fill("My first portfolio");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("checkbox", { name: "Add an account now" }).check();
  await page.getByLabel("Account name").fill("Cash wallet");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Review and save" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Save setup" }).click();
  const review = page.getByRole("region", { name: "Review", exact: true });
  await expect(review.getByRole("alert")).toContainText("A saved record conflicts");

  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(page.getByLabel("Account name")).toHaveValue("Cash wallet");
  await page.getByRole("checkbox", { name: "Add an account now" }).uncheck();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Review and save" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Save setup" }).click();
  await expect(page.getByRole("heading", { name: "Your portfolio is ready" })).toBeVisible();
  expect(runtime.writes).toEqual(["portfolios", "accounts"]);
});
