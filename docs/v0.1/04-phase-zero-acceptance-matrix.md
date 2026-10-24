# NEX-P0-05 — Phase 0 Acceptance Matrix

وضعیت: **Candidate**

تاریخ تصمیم: `2026-10-24`

هدف: اثبات کامل‌بودن Phase 0 و آماده‌سازی Freeze نهایی، بدون ساخت یا ادعای runtime

## 1. نتیجه مرحله

چهار تصمیم پیش‌نیاز به‌صورت مستقل فریز شده‌اند و P0-05 آن‌ها را در یک زنجیره
fail-closed جمع می‌کند. این candidate آماده اتصال به commit SHA و CI است، اما تا ثبت
Freeze نهایی مقدار `runtime_bootstrap_authorized=false` باقی می‌ماند. بنابراین گام مجاز
بعدی فقط `NEX-P0-05-FREEZE` است؛ پس از آن `NEX-P1-01` می‌تواند bootstrap واقعی runtime
را آغاز کند.

## 2. زنجیره Freeze

| تصمیم | موضوع | Freeze commit | شاهد ماشین‌خوان | وضعیت |
| --- | --- | --- | --- | --- |
| `NEX-P0-01` | Scope و مرز سیستم | `3327d9b4daa816eb271fa241247ad4ce21c708a3` | `artifacts/p0-01/scope-freeze.json` | Frozen |
| `NEX-P0-02` | Stack، معماری و repository | `386526c1324ffbf42e081dda0c362b5e92e21fce` | `artifacts/p0-02/technical-baseline-freeze.json` | Frozen |
| `NEX-P0-03` | API/Event/Export compatibility | `6243f0f28c6e7970d1323bad164e54b06bf2e173` | `artifacts/p0-03/integration-contract-freeze.json` | Frozen |
| `NEX-P0-04` | Security، private deployment و operations | `53e87e875d874f79def32468ece5dae43d8ddccf` | `artifacts/p0-04/security-boundary-freeze.json` | Frozen |
| `NEX-P0-05` | Acceptance و transition gate | پس از CI candidate ثبت می‌شود | Freeze record در commit جدا | Candidate |

Verifier ابتدا کل زنجیره P0-04 را اجرا می‌کند؛ verifier آن مرحله نیز به‌ترتیب P0-03،
P0-02 و P0-01 را بررسی می‌کند. در نتیجه یک freeze record منفرد نمی‌تواند جای پیش‌نیاز
خراب یا تغییرکرده را بگیرد.

## 3. ماتریس پذیرش

ماتریس کامل و ماشین‌خوان در
[`contracts/acceptance/v1/phase-zero-traceability.json`](../../contracts/acceptance/v1/phase-zero-traceability.json)
است. خلاصه دوازده الزام آن:

| ID | حوزه | Owner | تصمیم‌های منبع | وضعیت |
| --- | --- | --- | --- | --- |
| `NEX-P0-REQ-001` | Scope و system boundary | product_architecture | P0-01 | Pass |
| `NEX-P0-REQ-002` | Architecture، stack و data ownership | architecture | P0-02 | Pass |
| `NEX-P0-REQ-003` | TRD Bot contracts و compatibility | integration | P0-03 | Pass |
| `NEX-P0-REQ-004` | Identity، session، recovery و authorization | security | P0-04 | Pass |
| `NEX-P0-REQ-005` | Private deployment، secret و audit | security_operations | P0-04 | Pass |
| `NEX-P0-REQ-006` | SLO، capacity، retention، storage و recovery | operations | P0-04 | Pass |
| `NEX-P0-REQ-007` | Export-first و AI-safe evidence | data_governance | P0-01/P0-03 | Pass |
| `NEX-P0-REQ-008` | Forbidden capability inventory | security_architecture | P0-01..P0-04 | Pass |
| `NEX-P0-REQ-009` | Owner و evidence برای همه تصمیم‌ها | release | P0-01..P0-05 | Pass |
| `NEX-P0-REQ-010` | تعیین‌تکلیف debt | release | P0-02..P0-05 | Pass |
| `NEX-P0-REQ-011` | عدم ادعای runtime/production readiness | architecture | P0-02/P0-04/P0-05 | Pass |
| `NEX-P0-REQ-012` | اتصال transition به SHA و CI | release | P0-05 | Pass |

هر ردیف علاوه بر owner، مسیر evidence و verifierهای مسئول را ثبت می‌کند. مسیرهای خارج
از repository، evidence گم‌شده، verifier ناشناخته، ID تکراری و status غیر از `pass`
همگی fail-closed رد می‌شوند.

## 4. تعیین‌تکلیف Debt

| Debt | نتیجه | Owner/Due | توضیح |
| --- | --- | --- | --- |
| `NEX-DEBT-P0-02-001` | Transferred | `NEX-P1-01` | exact pin و lockfile فقط هنگام runtime bootstrap قابل تولید است |
| `NEX-DEBT-P0-02-002` | Closed | `NEX-P0-03` | schema و compatibility contract فریز شده‌اند |
| `NEX-DEBT-P0-02-003` | Closed | `NEX-P0-04` | identity/session/topology فریز شده‌اند |
| `NEX-DEBT-P0-02-004` | Closed | `NEX-P0-04` | SLO/retention/backup/capacity قابل اندازه‌گیری شده‌اند |
| `NEX-DEBT-P0-02-005` | Closed | `NEX-P0-05` | matrix و acceptance runner حاضرند |

Debt اول blocker مرحله صفر نیست، زیرا Phase 0 عمداً runtime dependency ندارد؛ اما
ورود به مرحله بعد آن را حذف نمی‌کند و `NEX-P1-01` بدون lockfile و exact resolution
پذیرفته نخواهد شد.

## 5. تصمیم‌های منتقل‌شده

- scaffold، exact dependency versions و lockfileها: `NEX-P1-01`؛
- schema دیتابیس، migration و durable jobs: Phase 1؛
- adapter اجرایی TRD Bot فقط پس از capability negotiation: Phase 1؛
- SaaS، multi-user، billing و federated identity: فاز محصول آینده؛
- انتخاب، آموزش، serving و monitoring مدل‌های ML: فاز مستقل AI/ML آینده.

این انتقال‌ها مجوز پیاده‌سازی زودهنگام نیستند. در v0.1 همچنان سیستم personal و
single-owner است و AI فقط از Exportهای دارای evidence، lineage و uncertainty تغذیه
خواهد شد.

## 6. مرز امنیتی عبور از Phase 0

موارد زیر همچنان وجود ندارند:

- Live order یا autonomous execution؛
- exchange credential یا wallet/fund transfer؛
- query مستقیم به دیتابیس TRD Bot؛
- public-internet production profile؛
- multi-tenant identity؛
- ادعای runtime، production readiness یا SLA خارجی.

تغییر هر مقدار این inventory به `true` باعث شکست acceptance runner می‌شود.

## 7. گیت Candidate

فرمان‌های زیر باید روی همان commit موفق باشند:

```bash
python3 scripts/verify_scope_contract.py
python3 scripts/verify_technical_baseline.py
python3 scripts/verify_integration_contracts.py
python3 scripts/verify_security_boundary.py
python3 scripts/verify_phase_zero_acceptance.py
python3 -m unittest discover -s tests -v
git diff --check
```

خروجی runner جدید باید شامل این markerها باشد:

```text
NEX_P0_04_PREREQUISITE=PASS
NEX_P0_05_PHASE_ZERO_ACCEPTANCE=PASS
```

## 8. Freeze نهایی

پس از commit و push این candidate، باید GitHub Actions برای **همان candidate SHA** تمام
jobهای scope، technical baseline، integration، security و phase-zero acceptance را
موفق کند. سپس فقط freeze record شامل SHA، URL و job evidence در commit جدا ثبت می‌شود.
تا آن لحظه `NEX-P1-01` مسدود است و این سند هیچ runtimeای را تحویل‌شده اعلام نمی‌کند.
