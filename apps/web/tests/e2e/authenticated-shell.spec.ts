import { createHash } from "node:crypto";

import { expect, type Page, test } from "@playwright/test";

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
  await expect(page.getByRole("heading", { name: "نمای کلی پرتفوی" })).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "حسابداری پرتفوی" })).toBeVisible();
  await expect(page.getByText("Opening evidence")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(sidebar).toBeHidden();
  await expect(page.getByRole("link", { name: "دفتر تراکنش", exact: true })).toHaveAttribute(
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
  await expect(page.locator(".workspace")).toHaveAttribute("inert", "");
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
  await expect(main).toBeFocused();
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
  await expect(page.getByRole("link", { name: "Alerts inbox", exact: true })).toHaveAttribute(
    "href",
    "/en/alerts",
  );

  await page.getByRole("link", { name: "Open evidence" }).click();
  const candidatePath = "/en/decisions/candidates/candidate-1";
  await expect(page).toHaveURL(candidatePath);
  await expect(page.getByRole("link", { name: "View linked alerts" })).toHaveAttribute(
    "href",
    "/en/alerts?decision=decision-evaluation-1",
  );
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
  await page.getByRole("link", { name: "Alerts inbox", exact: true }).click();
  await expect(page.getByText("Provider alert evidence is degraded")).toBeVisible();
  await expect(page.getByRole("heading", { name: "No active alerts" })).toBeVisible();
  await page.getByRole("link", { name: "Watchlists", exact: true }).click();
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

async function mockAcceptancePasskey(page: Page) {
  const origin = "http://localhost:3000";
  const device = await page.context().newCDPSession(page);
  await device.send("WebAuthn.enable");
  await device.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2",
      transport: "internal",
      hasResidentKey: true,
      hasUserVerification: true,
      automaticPresenceSimulation: true,
      isUserVerified: true,
    },
  });

  const setupCode = "fixture-only-setup-code".repeat(2);
  const registration = Buffer.alloc(32, 1).toString("base64url");
  const login = Buffer.alloc(32, 2).toString("base64url");
  const confirmation = Buffer.alloc(32, 3).toString("base64url");
  let credentialId: string | undefined;
  let signedIn = false;
  let verified = false;
  const session = () => ({
    owner_id: "acceptance-owner",
    recently_reauthenticated: verified,
    rotation_required: false,
  });

  await page.route("**/api/v1/auth/session", (route) =>
    signedIn
      ? route.fulfill({ json: session() })
      : route.fulfill({
          status: 401,
          json: { error: { code: "AUTHENTICATION_DENIED" } },
        }),
  );
  await page.route("**/api/v1/auth/bootstrap/options", (route) => {
    expect(route.request().postDataJSON()).toEqual({ bootstrap_token: setupCode });
    return route.fulfill({
      json: {
        algorithms: ["ES256"],
        challenge: registration,
        rp_id: "localhost",
        timeout_ms: 10_000,
      },
    });
  });
  await page.route("**/api/v1/auth/bootstrap/complete", (route) => {
    const { bootstrap_token, response_json } = route.request().postDataJSON();
    expect(bootstrap_token).toBe(setupCode);
    const credential = JSON.parse(response_json);
    expect(credential.type).toBe("public-key");
    expect(credential.response.attestationObject).toBeTruthy();
    const clientData = JSON.parse(
      Buffer.from(credential.response.clientDataJSON, "base64url").toString(),
    );
    expect(clientData).toMatchObject({ type: "webauthn.create", origin, challenge: registration });
    credentialId = credential.id;
    return route.fulfill({ json: { recovery_codes: ["fixture-recovery-code"] } });
  });

  for (const [operation, challenge] of [
    ["authentication", login],
    ["reauthentication", confirmation],
  ] as const) {
    await page.route(`**/api/v1/auth/${operation}/options`, (route) => {
      expect(credentialId).toBeTruthy();
      return route.fulfill({
        json: {
          allow_credentials: [{ credential_id: credentialId, transports: ["internal"] }],
          challenge,
          rp_id: "localhost",
          timeout_ms: 10_000,
        },
      });
    });
    await page.route(`**/api/v1/auth/${operation}/complete`, (route) => {
      const request = route.request().postDataJSON();
      expect(request).toMatchObject({ challenge, credential_id: credentialId });
      const assertion = JSON.parse(request.response_json);
      expect(assertion.id).toBe(credentialId);
      expect(assertion.response.signature).toBeTruthy();
      const clientData = JSON.parse(
        Buffer.from(assertion.response.clientDataJSON, "base64url").toString(),
      );
      expect(clientData).toMatchObject({ type: "webauthn.get", origin, challenge });
      signedIn = true;
      verified = operation === "reauthentication";
      return route.fulfill({ json: session() });
    });
  }

  return {
    origin,
    setupCode,
    expire() {
      signedIn = false;
      verified = false;
    },
    isVerified: () => verified,
  };
}

test("registers a passkey, restores the session, publishes an import and rebuilds holdings", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await mockPrivateRuntime(page);
  const identity = await mockAcceptancePasskey(page);

  await test.step("Bootstrap, sign in and restore an expired session", async () => {
    await page.goto(`${identity.origin}/en/login`);
    await page.getByRole("link", { name: "First-time setup" }).click();
    await page.getByLabel("One-time setup code").fill(identity.setupCode);
    await page.getByRole("button", { name: "Register owner passkey" }).click();
    await expect(page.getByRole("heading", { name: "Save recovery codes now" })).toBeVisible();
    await expect(page.getByText("fixture-recovery-code", { exact: true })).toBeVisible();
    await page.getByRole("link", { name: "I saved the recovery codes" }).click();
    await page.getByRole("button", { name: "Sign in with passkey" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
    await expect(page.getByText("Core portfolio", { exact: true }).first()).toBeVisible();

    identity.expire();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Session expired" })).toBeVisible();
    await page.getByRole("link", { name: "Go to sign in" }).click();
    await page.getByRole("button", { name: "Sign in with passkey" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
    await expect(page.locator(".application-shell")).toBeVisible();
  });

  let batchStatus: "dry_run" | "reviewed" | "published" | undefined;
  let rebuilt = false;
  const writes: string[] = [];
  const reason = "Checked the source records";
  const memo = "Imported acceptance entry";
  const importedAt = "2026-11-04T10:00:00Z";
  const quantity = "0.12345678";
  const legs = [
    { asset_id: "asset-btc", account_id: "account-1", quantity },
    { asset_id: "asset-btc", external_counterparty: "fixture-source", quantity: `-${quantity}` },
  ];
  const csvLegs = JSON.stringify(legs).replaceAll('"', '""');
  const csv = `row_id,portfolio_id,transaction_kind,occurred_at,memo,legs\nrow-1,portfolio-1,deposit,${importedAt},${memo},"${csvLegs}"`;
  const batch = () => ({
    import_batch_id: "acceptance-batch",
    content_sha256: createHash("sha256").update(csv).digest("hex"),
    created_at: importedAt,
    duplicate_count: 0,
    published_at: batchStatus === "published" ? importedAt : null,
    quarantined_count: 0,
    ready_count: 1,
    review_reason: batchStatus === "dry_run" ? null : reason,
    reviewed_at: batchStatus === "dry_run" ? null : importedAt,
    row_count: 1,
    rows: [
      {
        external_row_id: "row-1",
        import_row_id: "acceptance-import-row",
        normalized_payload: null,
        reason_code: null,
        row_number: 1,
        status: batchStatus === "published" ? "published" : "ready",
      },
    ],
    source_format: "csv",
    status: batchStatus,
  });
  await page.route("**/api/v1/imports", (route) =>
    route.fulfill({ json: { items: batchStatus ? [batch()] : [] } }),
  );
  await page.route("**/api/v1/imports/dry-runs", (route) => {
    expect(route.request().postDataJSON()).toEqual({ content: csv, source_format: "csv" });
    writes.push("preview");
    batchStatus = "dry_run";
    return route.fulfill({ json: batch() });
  });
  await page.route("**/api/v1/imports/acceptance-batch/reviews", (route) => {
    expect(route.request().postDataJSON()).toEqual({ reason });
    expect(batchStatus).toBe("dry_run");
    writes.push("review");
    batchStatus = "reviewed";
    return route.fulfill({ json: batch() });
  });
  await page.route("**/api/v1/imports/acceptance-batch/publication", (route) => {
    expect(identity.isVerified()).toBe(true);
    expect(batchStatus).toBe("reviewed");
    writes.push("publish");
    batchStatus = "published";
    return route.fulfill({ json: batch() });
  });
  await page.route("**/api/v1/transactions?**", (route) =>
    route.fulfill({
      json: {
        items:
          batchStatus === "published"
            ? [
                {
                  transaction_id: "acceptance-entry",
                  transaction_kind: "deposit",
                  occurred_at: importedAt,
                  recorded_at: importedAt,
                  source_kind: "import",
                  source_reference: "acceptance-batch",
                  memo,
                  legs: legs.map((leg, index) => ({
                    ...leg,
                    transaction_leg_id: `acceptance-leg-${index}`,
                  })),
                },
              ]
            : [],
      },
    }),
  );
  await page.route("**/api/v1/portfolios/portfolio-1/holdings?**", (route) =>
    rebuilt
      ? route.fulfill({
          json: {
            checkpoint: {
              cost_basis_method: "fifo",
              journal_sha256: "b".repeat(64),
              journal_transaction_count: 1,
              projection_version: "holdings-v1",
              rebuilt_at: importedAt,
            },
            items: [
              {
                account_id: "account-1",
                asset_id: "asset-btc",
                basis_status: "unknown",
                quantity,
                total_cost_basis: null,
                average_unit_cost: null,
                cost_basis_asset_id: null,
              },
            ],
          },
        })
      : route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } }),
  );
  await page.route("**/api/v1/portfolios/portfolio-1/holdings/rebuilds", (route) => {
    expect(route.request().postDataJSON()).toEqual({ cost_basis_method: "fifo" });
    expect(batchStatus).toBe("published");
    writes.push("rebuild");
    rebuilt = true;
    return route.fulfill({ json: {} });
  });

  await test.step("Preview, review and publish only after passkey verification and confirmation", async () => {
    await page.goto(`${identity.origin}/en/transactions/imports?portfolio=portfolio-1`);
    await page.getByLabel("Import content").fill(csv);
    expect(writes).toEqual([]);
    await page.getByRole("button", { name: "Create preview" }).click();
    await page.getByLabel("Reason", { exact: true }).fill(reason);
    await page.getByRole("button", { name: "Approve import" }).click();
    const review = page.getByRole("dialog", { name: "Approve this import?" });
    await expect(review).toContainText(reason);
    expect(writes).toEqual(["preview"]);
    await review.getByRole("button", { name: "Approve import" }).click();
    const publishButton = page.getByRole("button", { name: "Publish import", exact: true });
    await expect(publishButton).toBeDisabled();
    await page.getByRole("button", { name: "Verify with your passkey" }).click();
    await expect(publishButton).toBeEnabled();
    await publishButton.click();
    const publish = page.getByRole("dialog", { name: "Publish this import?" });
    await expect(publish).toContainText("acceptance-batch");
    expect(writes).toEqual(["preview", "review"]);
    await publish.getByRole("button", { name: "Publish import" }).click();
    const importBatch = page
      .getByRole("list", { name: "Import preview", exact: true })
      .getByRole("listitem")
      .filter({ has: page.getByText("acceptance-batch", { exact: true }) });
    await expect(
      importBatch.locator(".operation-card-heading").getByText("Published", { exact: true }),
    ).toBeVisible();
  });

  await test.step("Read the published entry and rebuild holdings from the selected journal", async () => {
    const accounting = page.getByRole("navigation", { name: "Portfolio accounting views" });
    await accounting.getByRole("link", { name: "Journal", exact: true }).click();
    await expect(page.getByText(memo, { exact: true })).toBeVisible();
    await accounting.getByRole("link", { name: "Holdings", exact: true }).click();
    await expect(page.getByText("No calculation is available", { exact: false })).toBeVisible();
    await page.getByRole("button", { name: "Rebuild from journal", exact: true }).click();
    const rebuild = page.getByRole("dialog", { name: "Rebuild accounting calculations?" });
    await expect(rebuild).toContainText("Core portfolio");
    expect(writes).toEqual(["preview", "review", "publish"]);
    await rebuild.getByRole("button", { name: "Rebuild from journal" }).click();
    await expect(page.getByText(`${quantity} BTC`, { exact: true })).toBeVisible();
    await expect(page.getByText("holdings-v1", { exact: true })).toBeVisible();
    expect(writes).toEqual(["preview", "review", "publish", "rebuild"]);
  });
});

test("monitoring preferences lead from a linked alert to its outcome journal", async ({ page }) => {
  await mockPrivateRuntime(page);
  const checksum = `sha256:${"a".repeat(64)}`;
  const watchlistId = "watchlist-1";
  const decisionId = "decision-evaluation-2";
  const primaryAlert = "critical-alert";
  const outcome = "Reviewed the linked alert after checking the evidence.";
  let entry: Record<string, unknown> | undefined;
  let journalWrites = 0;
  await page.route(`**/api/v1/decisions/${decisionId}/journal?**`, (route) =>
    route.fulfill({
      json: {
        decision_id: decisionId,
        items: entry ? [entry] : [],
        schema_version: "nexora-outcome-journal-v1",
      },
    }),
  );
  await page.route(`**/api/v1/decisions/${decisionId}/journal`, (route) => {
    const body = route.request().postDataJSON();
    expect(body).toMatchObject({ content: outcome, entry_kind: "owner_note" });
    expect(route.request().headers()["idempotency-key"]).toMatch(/^nexora-outcome-journal-/);
    journalWrites += 1;
    entry = {
      ...body,
      entry_id: "outcome-entry-1",
      decision_id: decisionId,
      decision_evidence_checksum: checksum,
      decision_evidence_generation: 3,
      recorded_at: new Date().toISOString(),
      author_kind: "owner",
      append_only: true,
      ai_generated: false,
      provider_rewritable: false,
    };
    return route.fulfill({ status: 201, json: entry });
  });
  let preferences = {
    include_resolved: false,
    minimum_severity: "info",
    presentation_order: "newest_first",
    updated_at: "2026-11-14T10:00:00Z",
  };
  let watchlistVersion = 2;
  const watchlist = () => ({
    watchlist_id: watchlistId,
    name: "Risk monitoring",
    created_at: "2026-11-14T10:00:00Z",
    updated_at: "2026-11-14T10:00:00Z",
    row_version: watchlistVersion,
    items: [],
    preferences,
  });
  await page.route("**/api/v1/watchlists?**", (route) =>
    route.fulfill({ json: { items: [watchlist()] } }),
  );
  await page.route(`**/api/v1/watchlists/${watchlistId}/preferences`, (route) => {
    const body = route.request().postDataJSON();
    expect(body).toEqual({
      expected_version: 2,
      include_resolved: false,
      minimum_severity: "critical",
      presentation_order: "newest_first",
    });
    preferences = { ...preferences, minimum_severity: body.minimum_severity };
    watchlistVersion += 1;
    return route.fulfill({ json: watchlist() });
  });

  let transition:
    | {
        alert_history_id: string;
        recorded_at: string;
        state: string;
        snooze_until: string;
        state_version: number;
      }
    | undefined;
  let alertWrites = 0;
  const alert = (id: string, severity: string, state: string) => ({
    alert_id: id,
    current_version: id === primaryAlert && transition ? transition.state_version : 0,
    evidence: { severity, evaluation_id: decisionId },
    history: id === primaryAlert && transition ? [transition] : [],
    local_state: id === primaryAlert && transition ? transition.state : state,
    snooze_until: id === primaryAlert ? (transition?.snooze_until ?? null) : null,
    source: {
      checksum,
      observed_at: "2026-11-14T10:00:00Z",
      resource_schema_version: "trd-bot-alert-v1",
    },
  });
  await page.route("**/api/v1/alerts?**", (route) =>
    route.fulfill({
      json: {
        items: [
          alert(primaryAlert, "critical", "open"),
          alert("low-severity-alert", "info", "open"),
          alert("resolved-alert", "critical", "resolved"),
        ],
        provider: { generation: 3, state: "ready" },
      },
    }),
  );
  await page.route(`**/api/v1/alerts/${primaryAlert}/state-transitions`, (route) => {
    alertWrites += 1;
    const body = route.request().postDataJSON();
    expect(body).toMatchObject({
      action: "snooze",
      evidence_generation: 3,
      expected_version: 0,
      source_evidence_checksum: checksum,
    });
    transition = {
      alert_history_id: "transition-1",
      recorded_at: new Date().toISOString(),
      state: "snoozed",
      snooze_until: body.snooze_until,
      state_version: 1,
    };
    return route.fulfill({ json: transition });
  });

  await page.goto(`/en/alerts/watchlists?watchlist=${watchlistId}`);
  await page.getByRole("combobox", { name: "Minimum visible severity" }).click();
  await page.getByRole("option", { name: "Critical" }).click();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Watchlist saved.")).toBeVisible();
  await page.getByRole("link", { name: "View alerts with these preferences" }).click();
  await expect(page).toHaveURL(`/en/alerts?watchlist=${watchlistId}`);
  await expect(page.getByRole("link", { name: primaryAlert })).toBeVisible();
  await expect(page.getByRole("heading", { name: "low-severity-alert" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "resolved-alert" })).toHaveCount(0);
  await page.getByRole("link", { name: primaryAlert }).click();
  await expect(page).toHaveURL(`/en/alerts?watchlist=${watchlistId}&alert=${primaryAlert}`);
  await page.getByRole("button", { name: "Snooze", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Snooze this alert?" });
  await expect(dialog).toContainText(primaryAlert);
  expect(alertWrites).toBe(0);
  await dialog.getByRole("button", { name: "Snooze", exact: true }).click();
  await expect(page.getByText("Alert updated.")).toBeVisible();
  await page.getByText("Alert history (1)", { exact: true }).click();
  await expect(page.getByText("Version 1 · Snoozed", { exact: true })).toBeVisible();
  expect(alertWrites).toBe(1);
  await page.getByRole("link", { name: "Open outcome journal" }).click();
  await expect(page).toHaveURL(`/en/journal?decision=${decisionId}`);
  await expect(page.getByLabel("Decision ID")).toHaveValue(decisionId);
  await expect(page.getByRole("heading", { name: "No journal entry yet" })).toBeVisible();
  await page.getByLabel("Occurred at", { exact: true }).fill("2026-11-14T10:00");
  await page.getByLabel("Owner-authored content").fill(outcome);
  await page.getByRole("button", { name: "Append entry" }).click();
  const entryDialog = page.getByRole("dialog", { name: "Append this entry?" });
  await expect(entryDialog).toContainText(decisionId);
  expect(journalWrites).toBe(0);
  await entryDialog.getByRole("button", { name: "Append entry" }).click();
  await expect(page.getByText("Entry added to the journal.")).toBeVisible();
  await expect(page.getByText(outcome, { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText(outcome, { exact: true })).toBeVisible();
  expect(journalWrites).toBe(1);
});

test("creates a private export receipt and verifies bytes before download", async ({ page }) => {
  await mockPrivateRuntime(page);
  const archive = Buffer.from("504b0506000000000000000000000000000000000000", "hex");
  const digest = createHash("sha256").update(archive).digest("hex");
  const id = `pex_${"a".repeat(24)}`;
  const version = `v1-${digest.slice(0, 16)}`;
  const path = `/v1/exports/portfolio-export/${id}/versions/${version}/download`;
  let writes = 0;
  let corrupt = true;
  await page.route("**/api/v1/portfolio-exports", (route) => {
    writes += 1;
    expect(route.request().postDataJSON()).toEqual({
      profile: "private_complete",
      formats: ["json", "csv"],
      pinned: true,
    });
    return route.fulfill({
      status: 201,
      json: {
        schema_version: "nexora-portfolio-export-publication-v1",
        manifest: {
          schema_version: "nexora-portfolio-export-manifest-v1",
          export_id: id,
          profile: "private_complete",
          delivery_format: "zip_bundle",
          content_formats: ["csv", "json"],
          generated_at: "2026-11-17T10:00:00Z",
          complete: true,
          public_download: false,
          snapshot_sha256: "b".repeat(64),
          record_count: 4,
        },
        artifact_version: version,
        artifact_sha256: digest,
        artifact_size_bytes: archive.length,
        retention_class: "pinned_export",
        download_path: path,
      },
    });
  });
  await page.route(`**/api${path}`, (route) => {
    const body = Buffer.from(archive);
    if (corrupt) body[0] ^= 1;
    return route.fulfill({
      headers: {
        "content-type": "application/zip",
        "x-artifact-sha256": digest,
        "content-length": String(body.length),
      },
      body,
    });
  });

  await page.goto("/en/exports");
  await page.getByRole("combobox", { name: "Export profile" }).click();
  await page.getByRole("option", { name: "Complete private export" }).click();
  await page.getByRole("checkbox", { name: "CSV" }).check();
  await page.getByRole("checkbox", { name: "Keep this export" }).check();
  await page.getByRole("button", { name: "Create export" }).click();
  const confirm = page.getByRole("dialog", { name: "Create this export?" });
  await expect(confirm).toContainText("Complete private export");
  expect(writes).toBe(0);
  await confirm.getByRole("button", { name: "Create export" }).click();
  await expect(page.getByText("Export created.")).toBeVisible();
  expect(writes).toBe(1);

  await page.reload();
  await expect(page.getByRole("heading", { name: "Complete private export" })).toBeVisible();
  const notifications = page.getByRole("region", { name: "Export notifications" });
  await page.getByRole("button", { name: "Verify file" }).click();
  await expect(notifications.getByText("The file did not pass verification")).toBeVisible();

  corrupt = false;
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download ZIP" }).click();
  const saved = await download;
  expect(saved.suggestedFilename()).toBe(`${id}.zip`);
  await expect(notifications.getByText("Verified ZIP download started.")).toBeVisible();
  expect(writes).toBe(1);
});

test("persists presentation settings and uses the chosen time zone for evidence", async ({
  page,
}) => {
  await mockPrivateRuntime(page);
  await page.goto("/fa/settings");
  await page.getByRole("link", { name: "English", exact: true }).click();
  await expect(page).toHaveURL("/en/settings");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.getByRole("combobox", { name: "Theme", exact: true }).click();
  await page.getByRole("option", { name: "Dark", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.getByRole("combobox", { name: "Display time zone" }).click();
  await page.getByRole("option", { name: "Tehran", exact: true }).click();
  await page.getByRole("combobox", { name: "Desktop sidebar" }).click();
  await page.getByRole("option", { name: "Collapsed", exact: true }).click();
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Display time zone" })).toHaveText("Tehran");
  await expect(page.locator(".application-shell")).toHaveAttribute(
    "data-sidebar-collapsed",
    "true",
  );
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("link", { name: "Manage watchlists" })).toHaveAttribute(
    "href",
    "/en/alerts/watchlists",
  );
  await expect(page.getByText("0.3.1", { exact: true })).toBeVisible();
  await page.goto("/en/decisions/candidates/candidate-1");
  await expect(page.locator('time[datetime="2026-11-14T10:00:00Z"]')).toContainText("13:30");
  await page.goto("/");
  await expect(page).toHaveURL("/en/overview");
});

const workspaceAuditRoutes = [
  "onboarding",
  "overview",
  "assets",
  "portfolios",
  "portfolios/portfolio-1",
  "accounts",
  "transactions",
  "transactions/holdings?portfolio=portfolio-1",
  "transactions/lots?portfolio=portfolio-1",
  "transactions/imports",
  "transactions/reconciliation",
  "decisions",
  "decisions/records/decision-evaluation-2",
  "decisions/candidates/candidate-1",
  "decisions/candidates/candidate-1/risk",
  "decisions/candidates/candidate-1/impact",
  "decisions/candidates/candidate-1/scenarios",
  "decisions/candidates/candidate-1/reviews",
  "alerts",
  "alerts/watchlists",
  "journal?decision=decision-evaluation-2",
  "exports",
  "settings",
] as const;

for (const [index, width] of [320, 768, 1280, 1920].entries()) {
  for (const locale of ["en", "fa"] as const) {
    const theme = (index % 2 === 0) === (locale === "en") ? "light" : "dark";
    test(`workspace audit · ${locale} · ${theme} · ${width}px`, async ({ page }) => {
      test.setTimeout(120_000);
      await mockPrivateRuntime(page);
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });

      for (const route of ["login", "bootstrap", ...workspaceAuditRoutes]) {
        await test.step(route, async () => {
          await page.goto(`/${locale}/${route}`);
          const html = page.locator("html");
          await expect(html).toHaveAttribute("lang", locale);
          await expect(html).toHaveAttribute("dir", locale === "fa" ? "rtl" : "ltr");
          await expect(html).toHaveAttribute("data-theme", theme);
          const main = page.getByRole("main");
          await expect(main.getByRole("heading", { level: 1 })).toBeVisible();

          if (route !== "login" && route !== "bootstrap") {
            await expect(page.locator(".application-shell")).toBeVisible();
          }
          await expect(main.locator(".nx-spinner")).toHaveCount(0);
          await page.evaluate(() => document.fonts.ready.then(() => undefined));
          const documentFits = await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          );
          expect(documentFits, `Viewport overflow on /${locale}/${route} at ${width}px`).toBe(true);
        });
      }
    });
  }
}

test("language switch keeps a journal link and the back-to-content shortcut is reachable", async ({
  page,
}) => {
  await mockPrivateRuntime(page);
  await page.goto("/en/journal?decision=decision-evaluation-2");
  await expect(page.getByRole("heading", { level: 1, name: "Journal" })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.locator("a.skip-link");
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByRole("link", { name: "Language: فارسی" }).click();
  await expect(page).toHaveURL("/fa/journal?decision=decision-evaluation-2");
  await expect(page.getByRole("heading", { level: 1, name: "دفتر نتایج" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "شناسهٔ تصمیم" })).toHaveValue(
    "decision-evaluation-2",
  );
});
