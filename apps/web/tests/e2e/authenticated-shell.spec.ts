import { expect, test } from "@playwright/test";

async function mockPrivateRuntime(page: import("@playwright/test").Page) {
  let reviewRecorded = false;
  const provider = {
    contract_version: "nexora-trd-integration-v1",
    generation: 3,
    provider_version: "0.3.1",
    reason_code: "ACTIVE_PROJECTION_READY",
    state: "ready",
  };
  const source = (resourceType: string, resourceId: string) => ({
    aggregate_id: resourceId,
    aggregate_type: resourceType,
    aggregate_version: 2,
    checksum: `sha256:${"a".repeat(64)}`,
    event_id: "event-2",
    observed_at: "2026-11-14T10:00:00Z",
    resource_id: resourceId,
    resource_schema_version: `trd-bot-${resourceType.replaceAll("_", "-")}-v1`,
    resource_type: resourceType,
    schema_version: "nexora-source-reference-v1",
    source_product: "trd_bot",
    source_version: "0.3.1",
  });
  const candidate = {
    decision_kind: "candidate",
    evidence: {
      candidate_id: "candidate-1",
      evaluation_id: "decision-evaluation-1",
      external_order_submission_allowed: false,
      offline_only: true,
    },
    evidence_sha256: "b".repeat(64),
    local_state: "review_pending",
    resource_id: "candidate-1",
    resource_type: "candidate",
    source: source("candidate", "candidate-1"),
  };
  const decision = {
    decision_kind: "portfolio_assessment",
    evidence: { recommendation: "review" },
    evidence_sha256: "c".repeat(64),
    local_state: "review_pending",
    resource_id: "decision-evaluation-2",
    resource_type: "decision_evaluation",
    source: source("decision_evaluation", "decision-evaluation-2"),
  };
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
        positions: [
          {
            account_id: "account-1",
            asset_id: "asset-btc",
            basis_status: "known",
            evidence_at: "2026-11-03T11:55:00Z",
            market_value: "12500",
            quantity: "0.12500001",
            state: "fresh",
          },
        ],
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
  await page.route("**/api/v1/portfolios/portfolio-1/performance?**", (route) => {
    const query = new URL(route.request().url()).searchParams;
    const start = query.get("start_at")!;
    const end = query.get("end_at")!;
    const sampleTime = (fraction: number) =>
      new Date(Date.parse(start) + (Date.parse(end) - Date.parse(start)) * fraction).toISOString();
    return route.fulfill({
      json: {
        start_at: start,
        end_at: end,
        points: [
          {
            as_of: start,
            nav: "11500",
            external_flow: "0",
            period_return: null,
            cumulative_return: "0",
            state: "available",
            reason_code: null,
          },
          {
            as_of: sampleTime(1 / 3),
            nav: "12500",
            external_flow: "137.5",
            period_return: "0.075",
            cumulative_return: "0.075",
            state: "stale",
            reason_code: null,
          },
          {
            as_of: sampleTime(2 / 3),
            nav: "12600",
            external_flow: null,
            period_return: null,
            cumulative_return: null,
            state: "unavailable",
            reason_code: "MISSING_EXTERNAL_FLOW_VALUATION",
          },
          {
            as_of: end,
            nav: "12500",
            external_flow: "0",
            period_return: "-0.0079365079365",
            cumulative_return: null,
            state: "available",
            reason_code: null,
          },
        ],
      },
    });
  });
  await page.route("**/api/v1/transactions?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [
          {
            correction_kind: null,
            correction_of_transaction_id: null,
            legs: [
              {
                account_id: "account-1",
                asset_id: "asset-btc",
                external_counterparty: null,
                quantity: "1.25",
                sequence: 1,
                transaction_leg_id: "leg-1",
              },
              {
                account_id: null,
                asset_id: "asset-usd",
                external_counterparty: "market",
                quantity: "-10000",
                sequence: 2,
                transaction_leg_id: "leg-2",
              },
            ],
            memo: "Opening evidence",
            occurred_at: "2026-11-03T10:00:00Z",
            recorded_at: "2026-11-03T10:01:00Z",
            source_kind: "manual",
            source_reference: "owner-entry",
            transaction_id: "transaction-1",
            transaction_kind: "buy",
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/portfolios/portfolio-1/holdings?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        checkpoint: {
          cost_basis_method: "fifo",
          holdings_rebuild_id: "rebuild-1",
          journal_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          journal_transaction_count: 1,
          last_transaction_id: "transaction-1",
          portfolio_id: "portfolio-1",
          projection_version: "holdings-v1",
          rebuilt_at: "2026-11-03T12:00:00Z",
        },
        items: [],
      },
    }),
  );
  await page.route("**/api/v1/portfolios/portfolio-1/lots?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        checkpoint: {
          cost_basis_method: "fifo",
          holdings_rebuild_id: "rebuild-1",
          journal_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          journal_transaction_count: 1,
          last_transaction_id: "transaction-1",
          portfolio_id: "portfolio-1",
          projection_version: "holdings-v1",
          rebuilt_at: "2026-11-03T12:00:00Z",
        },
        items: [],
      },
    }),
  );
  await page.route("**/api/v1/imports", (route) =>
    route.fulfill({ contentType: "application/json", json: { items: [] } }),
  );
  await page.route("**/api/v1/reconciliation-cases", (route) =>
    route.fulfill({ contentType: "application/json", json: { items: [] } }),
  );
  await page.route("**/api/v1/decisions?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [candidate, decision],
        next_cursor: null,
        provider,
        schema_version: "nexora-decision-feed-v1",
      },
    }),
  );
  await page.route("**/api/v1/candidates/candidate-1", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        candidate: { ...candidate, evidence: { ...candidate.evidence, signal: "observe" } },
        provider,
        schema_version: "nexora-decision-feed-v1",
      },
    }),
  );
  await page.route("**/api/v1/risk-gates/decision-evaluation-1", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        provider,
        risk_gate: {
          approved_candidate_id: "candidate-1",
          candidate_id: "candidate-1",
          checks: [
            {
              actual_value: "0.40",
              explanation: "Ranking score meets the policy floor.",
              limit_value: "0.30",
              name: "ranking_score",
              passed: true,
            },
          ],
          decision: "approved",
          disposition: "accepted",
          evaluated_at: "2026-11-14T10:00:00Z",
          evidence_sha256: "d".repeat(64),
          external_order_submission_allowed: false,
          offline_only: true,
          policy: { checksum: "e".repeat(64), version: "decision-risk-v1" },
          position_sizing_exposed: false,
          provider_reason_codes: [],
          source: source("risk_gate", "decision-evaluation-1"),
          uncertainty: {
            reason_code: "TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED",
            state: "not_supplied",
            value: null,
          },
        },
        schema_version: "nexora-risk-gate-explanation-v1",
      },
    }),
  );
  await page.route("**/api/v1/portfolio-impacts/decision-evaluation-1", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        portfolio_impact: {
          analysis: {
            candidate_id: "candidate-1",
            checks: [],
            correlation: {
              evidence: "No comparable open position.",
              maximum_absolute_correlation: null,
              status: "not_applicable",
            },
            exposure: {
              candidate_notional: "1000.00000000",
              current_exposure_fraction: "0.000000",
              current_gross_notional: "0.00000000",
              projected_asset_concentration_fraction: "0.100000",
              projected_exposure_fraction: "0.100000",
              projected_gross_notional: "1000.00000000",
            },
            recommendation: "accept",
            scenarios: [
              {
                candidate_pnl: "-100.00000000",
                existing_pnl: "0.00000000",
                loss_fraction: "0.010000",
                projected_equity: "9900.00000000",
                shock_fraction: "-0.100000",
              },
            ],
            snapshot: {
              as_of: "2026-11-14T10:00:00Z",
              mode: "paper",
              open_positions: [],
              source: "empty_baseline",
            },
          },
          analyzed_at: "2026-11-14T10:00:00Z",
          candidate_id: "candidate-1",
          disposition: "accepted",
          evidence_sha256: "f".repeat(64),
          external_order_submission_allowed: false,
          order_intent_created: false,
          policy: { checksum: "9".repeat(64), version: "decision-portfolio-v1" },
          provider_reason_codes: [],
          recommendation: "accept",
          risk_gate_checksum_cross_validated: true,
          snapshot_id: "snapshot-1",
          transaction_created: false,
          uncertainty: {
            reason_code: "TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED",
            state: "not_supplied",
            value: null,
          },
        },
        provider,
        schema_version: "nexora-portfolio-candidate-impact-v1",
      },
    }),
  );
  await page.route("**/api/v1/decisions/*/reviews", (route) => {
    const decisionId = new URL(route.request().url()).pathname.split("/")[4];
    const review = {
      action: "accept",
      decision_id: decisionId,
      delivery_status: "accepted",
      order_intent_created: false,
      reason_code: "owner.accept.evidence_sufficient",
      reason_note: null,
      recorded_at: "2026-11-18T10:00:01Z",
      review_id: "review-1",
      review_version: 1,
      reviewed_at: "2026-11-18T10:00:00Z",
      transaction_created: false,
    };
    if (route.request().method() === "POST") {
      reviewRecorded = true;
      return route.fulfill({ contentType: "application/json", json: review });
    }
    return route.fulfill({
      contentType: "application/json",
      json: {
        current_version: reviewRecorded ? 1 : 0,
        decision_id: decisionId,
        evidence_generation: 3,
        latest_review_id: reviewRecorded ? "review-1" : null,
        local_state: reviewRecorded ? "accepted" : "review_pending",
        provider_delivery_required: true,
        reviewable: true,
        reviews: reviewRecorded ? [review] : [],
        schema_version: "nexora-human-decision-review-v1",
        source_evidence_checksum: `sha256:${"a".repeat(64)}`,
      },
    });
  });
  await page.route("**/api/v1/decisions/*/journal?**", (route) => {
    const decisionId = new URL(route.request().url()).pathname.split("/")[4];
    return route.fulfill({
      contentType: "application/json",
      json: {
        decision_id: decisionId,
        items: [],
        schema_version: "nexora-outcome-journal-v1",
      },
    });
  });
  await page.route("**/api/v1/alerts?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [],
        notification_delivery_enabled: false,
        provider,
        schema_version: "nexora-alert-inbox-v1",
      },
    }),
  );
  await page.route("**/api/v1/watchlists?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [],
        schema_version: "nexora-watchlists-v1",
      },
    }),
  );
}

test("Persian authenticated shell is RTL and responsive", async ({ page }) => {
  await mockPrivateRuntime(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/fa");
  await expect(page).toHaveURL("/fa/overview");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("نمای کلی");
  await expect(page.locator(".ready-badge")).toHaveText("نشست مالک فعال است");
  await expect(page.getByRole("heading", { name: "نمای کلی پورتفولیو" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "دفتر حساب‌ها" })).toBeVisible();
  const sidebar = page.locator("#desktop-sidebar");
  const main = page.getByRole("main");
  expect((await sidebar.boundingBox())!.x).toBeGreaterThan((await main.boundingBox())!.x);

  await page.getByRole("button", { name: "جمع کردن نوار کناری" }).click();
  await expect(page.getByRole("button", { name: "باز کردن نوار کناری" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await page.getByRole("link", { name: "تراکنش‌ها" }).click();
  await expect(page).toHaveURL("/fa/transactions");
  await expect(page.getByRole("link", { name: "تراکنش‌ها" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByRole("heading", { name: "ژورنال، دارایی‌ها و تطبیق" })).toBeVisible();
  await expect(page.getByText("Opening evidence")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(sidebar).toBeHidden();
  await expect(page.getByRole("link", { name: "ژورنال", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );

  const menu = page.getByRole("button", { name: "باز کردن منو" });
  await menu.focus();
  await menu.press("Enter");
  const drawer = page.getByRole("dialog", { name: "منوی فضای کاری" });
  await expect(drawer.getByRole("button", { name: "بستن منو" })).toBeFocused();
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("hidden");
  const close = drawer.getByRole("button", { name: "بستن منو" });
  await close.press("Shift+Tab");
  await expect(drawer.getByRole("link", { name: "تنظیمات" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(menu).toBeFocused();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe("");

  await menu.click();
  await drawer.getByRole("link", { name: "تصمیم‌ها" }).click();
  await expect(page).toHaveURL("/fa/decisions");
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("heading", { name: "فضای کاری هوشمندی تصمیم" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "تصمیم‌ها و پیشنهادها", exact: true }),
  ).toBeVisible();
});

test("shows sampled performance gaps and precise holdings on a Persian mobile page", async ({
  page,
}) => {
  await mockPrivateRuntime(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/fa/portfolios/portfolio-1");

  const holdings = page.getByRole("table", { name: "موجودی دارایی‌ها" });
  await expect(holdings).toContainText("۰٫۱۲۵۰۰۰۰۱");
  await expect(holdings).toContainText("Brokerage");

  const performance = page.getByRole("region", { name: "عملکرد پرتفوی" });
  const range = performance.getByRole("combobox", { name: "بازهٔ زمانی عملکرد", exact: true });
  await range.click();
  const requestedWeek = page.waitForRequest(
    (request) =>
      request.url().includes("/performance?") &&
      new URL(request.url()).searchParams.get("point_count") === "8",
  );
  await performance
    .getByRole("listbox", { name: "بازهٔ زمانی عملکرد", exact: true })
    .getByRole("option", { name: "۷ روز گذشته", exact: true })
    .click();
  const query = new URL((await requestedWeek).url()).searchParams;
  expect(query.get("end_at")).toBe("2026-11-03T12:00:00Z");
  expect(query.get("start_at")).toBe("2026-10-27T12:00:00.000Z");

  await expect(performance.locator(".performance-chart-line")).toHaveCount(1);
  await expect(performance.locator(".performance-chart-line[data-stale]")).toHaveCount(1);
  await expect(
    performance.getByRole("heading", { name: "ارزش خالص دارایی در آغاز و پایان بازه" }),
  ).toBeVisible();
  await performance.getByText("نمایش داده‌های عملکرد", { exact: true }).click();
  const data = performance.getByRole("table", { name: "داده‌های عملکرد" });
  await expect(data).toContainText("۷٫۵۰٪");
  await expect(data).toContainText("ارزش یک واریز یا برداشت مشخص نیست.");
  await expect(data).toContainText("بازده یکی از بازه‌های قبلی در دسترس نیست.");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

test("English workspace routes share a left sidebar and support portfolio deep links", async ({
  page,
}) => {
  await mockPrivateRuntime(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/en");
  await expect(page).toHaveURL("/en/overview");
  const navigation = page.getByRole("navigation", { name: "Workspace navigation" });
  await expect(navigation).toBeVisible();
  expect((await navigation.boundingBox())!.x).toBeLessThan(
    (await page.getByRole("main").boundingBox())!.x,
  );

  await navigation.getByRole("link", { name: "Portfolios" }).click();
  await expect(page).toHaveURL("/en/portfolios");
  await page.getByRole("link", { name: "View portfolio details" }).click();
  await expect(page).toHaveURL("/en/portfolios/portfolio-1");
  await expect(page.getByRole("heading", { name: "Core portfolio" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brokerage" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Portfolios" })).toHaveAttribute(
    "aria-current",
    "location",
  );

  for (const [path, title] of [
    ["alerts", "Alerts"],
    ["journal", "Journal"],
    ["exports", "Exports"],
    ["settings", "Settings"],
  ]) {
    await navigation.getByRole("link", { name: title, exact: true }).click();
    await expect(page).toHaveURL(`/en/${path}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
  }

  await page.goto("/en/portfolios/missing");
  await expect(page.getByRole("heading", { name: "Portfolio not found" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brokerage" })).toHaveCount(0);
});

test("Decision workflow is keyboard integrated and uses routed evidence", async ({ page }) => {
  await mockPrivateRuntime(page);
  await page.goto("/en/decisions");

  await expect(
    page.getByRole("heading", { name: "Decision intelligence workspace" }),
  ).toBeVisible();
  const candidateButton = page.getByRole("button", { name: /candidate-1/i });
  await expect(candidateButton).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Active Decision context" }),
  ).toContainText("decision-evaluation-1");
  await expect(page.getByText("Journal for Decision")).toBeVisible();
  await expect(page.getByText("No journal entry yet")).toBeVisible();

  await candidateButton.focus();
  await candidateButton.press("End");
  const secondDecision = page.getByRole("button", { name: /decision-evaluation-2/i });
  await expect(secondDecision).toBeFocused();
  await expect(
    page.getByRole("status").filter({ hasText: "Active Decision context" }),
  ).toContainText("decision-evaluation-2");

  await secondDecision.press("Home");
  await expect(candidateButton).toBeFocused();
  await expect(page.getByRole("heading", { name: "No active alerts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No watchlist yet" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Alerts", exact: true })).toHaveAttribute(
    "href",
    "/en/alerts",
  );

  await page.getByRole("link", { name: "Open evidence" }).click();
  const candidatePath = "/en/decisions/candidates/candidate-1";
  await expect(page).toHaveURL(candidatePath);
  const sections = page.getByRole("navigation", { name: "Decision evidence pages" });

  await sections.getByRole("link", { name: "Risk Gate" }).click();
  await expect(page).toHaveURL(`${candidatePath}/risk`);
  await expect(page.getByRole("heading", { name: "Risk Gate explanation" })).toBeVisible();
  await expect(page.getByText("decision-risk-v1")).toBeVisible();
  await sections.getByRole("link", { name: "Portfolio impact" }).click();
  await expect(page).toHaveURL(`${candidatePath}/impact`);
  await expect(page.getByRole("heading", { name: "Candidate portfolio impact" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Exposure as a share of equity" })).toBeVisible();
  await sections.getByRole("link", { name: "Scenarios" }).click();
  const scenarioTable = page.getByRole("table", { name: "Scenarios" });
  await expect(scenarioTable.getByText("9900.00000000", { exact: true })).toBeVisible();

  const reviewRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/reviews")) {
      reviewRequests.push(request.url());
    }
  });
  await sections.getByRole("link", { name: "Reviews" }).click();
  await expect(page).toHaveURL(`${candidatePath}/reviews`);
  await expect(page.getByRole("heading", { name: "Accept, reject or defer" })).toBeVisible();
  await page.getByRole("button", { name: "Record immutable review" }).click();
  const confirm = page.getByRole("dialog", { name: "Record this review?" });
  await expect(confirm).toContainText("decision-evaluation-1");
  expect(reviewRequests).toHaveLength(0);
  await confirm.getByRole("button", { name: "Record immutable review" }).click();
  await expect(page.getByText("Accept · v1")).toBeVisible();
  expect(reviewRequests).toHaveLength(1);
});

test("Decision evidence can be opened directly on a Persian mobile page", async ({ page }) => {
  await mockPrivateRuntime(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/fa/decisions/records/decision-evaluation-2");
  await expect(page.getByRole("heading", { name: "decision-evaluation-2" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  const navigation = page.getByRole("navigation", { name: "صفحه‌های شواهد تصمیم" });
  await expect(navigation.getByRole("link", { name: "شواهد", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

test("Phase 3 surfaces degraded, empty and error states explicitly", async ({ page }) => {
  await mockPrivateRuntime(page);
  let releaseDecision: () => void = () => undefined;
  const decisionGate = new Promise<void>((resolve) => {
    releaseDecision = resolve;
  });
  const degradedProvider = {
    contract_version: null,
    generation: null,
    provider_version: null,
    reason_code: "ACTIVE_PROJECTION_UNAVAILABLE",
    state: "degraded",
  };
  await page.route("**/api/v1/decisions?**", async (route) => {
    await decisionGate;
    await route.fulfill({
      contentType: "application/json",
      json: {
        items: [],
        next_cursor: null,
        provider: degradedProvider,
        schema_version: "nexora-decision-feed-v1",
      },
    });
  });
  await page.route("**/api/v1/alerts?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      json: {
        items: [],
        notification_delivery_enabled: false,
        provider: degradedProvider,
        schema_version: "nexora-alert-inbox-v1",
      },
    }),
  );
  await page.route("**/api/v1/watchlists?**", (route) => route.abort("failed"));

  await page.goto("/en/decisions");
  await expect(page.getByText("Loading the active decision projection…")).toBeVisible();
  releaseDecision();
  await expect(page.getByText("Provider evidence is degraded")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No Decision or Candidate evidence" }),
  ).toBeVisible();
  await expect(page.getByText("Provider alert evidence is degraded")).toBeVisible();
  await expect(page.getByRole("heading", { name: "No active alerts" })).toBeVisible();
  await expect(
    page.getByText("Watchlists could not be loaded. No preference was changed."),
  ).toBeVisible();
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

test("accounting routes preserve context and import files stay local until preview", async ({
  page,
}) => {
  await mockPrivateRuntime(page);
  let previewRequests = 0;
  const csv = "external_row_id,portfolio_key\nrow-1,core";
  await page.route("**/api/v1/imports/dry-runs", async (route) => {
    previewRequests += 1;
    expect(route.request().postDataJSON()).toEqual({ content: csv, source_format: "csv" });
    await route.fulfill({ json: {} });
  });

  await page.goto("/en/transactions/holdings?portfolio=portfolio-1");
  const navigation = page.getByRole("navigation", { name: "Portfolio accounting views" });
  await expect(navigation.getByRole("link", { name: "Holdings", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByText("This calculation has no holdings.")).toBeVisible();

  const weightedHoldings = page.waitForRequest(
    (request) =>
      new URL(request.url()).pathname.endsWith("/portfolio-1/holdings") &&
      new URL(request.url()).searchParams.get("cost_basis_method") === "weighted_average",
  );
  await page.getByRole("combobox", { name: "Cost-basis method" }).click();
  await page.getByRole("option", { name: "Weighted average" }).click();
  await weightedHoldings;
  await expect(page).toHaveURL(
    "/en/transactions/holdings?portfolio=portfolio-1&basis=weighted_average",
  );

  const weightedLots = page.waitForRequest(
    (request) =>
      new URL(request.url()).pathname.endsWith("/portfolio-1/lots") &&
      new URL(request.url()).searchParams.get("cost_basis_method") === "weighted_average",
  );
  await navigation.getByRole("link", { name: "Purchase lots" }).click();
  await weightedLots;
  await expect(page).toHaveURL(
    "/en/transactions/lots?portfolio=portfolio-1&basis=weighted_average",
  );
  await expect(page.getByText("This calculation has no open purchase lots.")).toBeVisible();

  await navigation.getByRole("link", { name: "Imports", exact: true }).click();
  await expect(page).toHaveURL(
    "/en/transactions/imports?portfolio=portfolio-1&basis=weighted_average",
  );
  await page.getByLabel("Choose an import file", { exact: false }).setInputFiles({
    buffer: Buffer.from(csv),
    mimeType: "text/csv",
    name: "records.csv",
  });
  await expect(page.getByLabel("Import content")).toHaveValue(csv);
  expect(previewRequests).toBe(0);
  await page.getByRole("button", { name: "Create preview" }).click();
  await expect(page.getByText("Operation completed.")).toBeVisible();
  await expect(page.getByLabel("Import content")).toHaveValue("");
  expect(previewRequests).toBe(1);

  await navigation.getByRole("link", { name: "Reconciliation", exact: true }).click();
  await expect(page).toHaveURL(
    "/en/transactions/reconciliation?portfolio=portfolio-1&basis=weighted_average",
  );
  await expect(page.getByText("No reconciliation case requires review.")).toBeVisible();
});
