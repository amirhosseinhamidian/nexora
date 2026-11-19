# NEX-P4-11 Product end-to-end acceptance

P4-11 binds the browser journeys and the owner's visual review to the same
candidate commit and tree. The [P4-10 Freeze record](../../artifacts/p4-10/experience-hardening-ui-freeze.json)
is committed at `d4896ec250c8f70fedcd42b488235a8099e37f17`, and its
[CI run](https://github.com/amirhosseinhamidian/nexora/actions/runs/44499153316)
passed. The [acceptance contract](../../contracts/nexora-v0.1-phase-four-product-acceptance.json)
defines the required evidence.

## Browser journeys

| Journey | Expected result |
| --- | --- |
| Setup, sign-in and session recovery | Chromium registers a passkey with a virtual authenticator, displays recovery codes, signs in and restores access after expiry. Overview shows the available portfolio. |
| First portfolio | Setup creates an asset, a portfolio and an optional account. The owner can recover an already-saved account after a lost response or continue without adding an account. |
| Import and holdings | Preview and review precede publication. Publishing requires recent passkey verification and confirmation. The published entry appears in the journal, and a confirmed rebuild displays the expected quantity and calculation details. |
| Decision review | The owner navigates from Decision evidence to a Candidate and records a review against its evidence. |
| Alert and outcome journal | The alert transition and journal entry retain their link to the Decision evidence. |
| Export | The owner confirms a private export, verifies its bytes and downloads it. |

Chromium exercises the WebAuthn API with a virtual authenticator. The private
API responses, portfolio data and provider evidence are synthetic fixtures.
The browser job requires each listed case and the eight P4-10 viewport
cases to pass. It uploads `p4-11-browser-evidence`, which carries the
candidate commit and tree, workflow run and attempt, case results and the
SHA-256 of the Playwright report.
[Chromium WebAuthn protocol](https://chromium.googlesource.com/chromium/src/+/530cafad9050e539f69b1178d75cf253814ae57b/third_party/blink/public/devtools_protocol/domains/WebAuthn.pdl).

## Local candidate verification

```zsh
eval "$(fnm env --shell zsh)"
fnm use 24.22.1

./apps/web/node_modules/.bin/prettier --config apps/web/prettier.config.mjs --write \
  apps/web/tests/e2e/authenticated-shell.spec.ts \
  contracts/nexora-v0.1-phase-four-product-acceptance.json \
  .github/workflows/phase-four-product-acceptance.yml
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e

.venv/bin/python scripts/verify_experience_hardening_ui.py
.venv/bin/python scripts/verify_phase_four_product_acceptance.py
.venv/bin/python -m unittest discover -s tests -v
```

## بررسی دستی ظاهر پس از ثبت کامیت نامزد

وب را از همان کامیت بسازید و در محیط خصوصی محلی با دادهٔ آزمایشی اجرا کنید.
در ابزار مرورگر، عرض صفحه را ۳۲۰، ۷۶۸، ۱۲۸۰ و ۱۹۲۰ پیکسل تنظیم کنید
و در هر عرض هر دو زبان را با هر دو پوستهٔ روشن و تاریک مرور کنید.
در هر یک از ۱۶ حالت این موارد را بررسی کنید.

- صفحهٔ ورود، راه‌اندازی و ثبت پرتفوی خوانا باشند. برچسب فیلد، متن خطا و
  دکمهٔ ادامه یا تلاش دوباره در دسترس باشند.
- نوار کناری در فارسی سمت راست و در انگلیسی سمت چپ باشد. در صفحهٔ باریک
  منو باز و بسته شود و در صفحهٔ عریض بتوان نوار کناری را جمع کرد.
- در نمای کلی و پرتفوی، نمودار، مقادیر و جدول‌ها خوانا باشند و صفحه
  پیمایش افقی سراسری نداشته باشد. در صورت نیاز، جدول در محدودهٔ خودش
  به طرفین پیمایش شود.
- در دفتر تراکنش، ورود داده، دارایی‌ها، تصمیم‌ها، هشدارها، دفتر نتایج و
  خروجی‌ها، پیوندها، متن‌ها و دکمه‌ها واضح باشند. شناسه‌ها و عددهای ترکیبی
  به ترتیب درست نمایش داده شوند.
- با کلیدهای Tab و Shift+Tab به دکمه‌ها و گزینه‌ها برسید. در پنجرهٔ
  تأیید، تمرکز قابل مشاهده باشد، Escape پنجره را ببندد و تمرکز به دکمهٔ
  بازکننده برگردد. پیام‌های موفقیت، هشدار و خطا قابل تشخیص باشند.

از مخزن تمیزِ همان کامیت، فرم ثبت نتیجه را بسازید.

```zsh
NEXORA_P411_MANUAL="/tmp/nexora-p4-11-$(git rev-parse --short HEAD)-visual.json"
.venv/bin/python scripts/verify_phase_four_product_acceptance.py manual-template "$NEXORA_P411_MANUAL"
```

در فایل، پس از بررسی هر ردیف، مقدار `result` را به `pass` یا `fail`
تغییر دهید. اگر ایرادی دیدید، مسیر صفحه و شرح کوتاه را همراه نتیجه ثبت کنید.
کد راه‌اندازی، کد بازیابی، اطلاعات شخصی و داده‌های واقعی حساب‌ها را در فایل
قرار ندهید. سپس فرمان زیر را در همان کامیت اجرا کنید.

```zsh
.venv/bin/python scripts/verify_phase_four_product_acceptance.py verify-manual "$NEXORA_P411_MANUAL"
```

## Freeze

`NEX-P4-11` is frozen at candidate `102a3c711e72aeecfb75b505d5afa890628c762c`.
The contract and browser jobs passed in
[GitHub Actions run 44506955235](https://github.com/amirhosseinhamidian/nexora/actions/runs/44506955235).
The owner confirmed all 16 visual profiles on the same candidate.
The [Freeze record](../../artifacts/p4-11/phase-four-product-acceptance-freeze.json)
stores both evidence records, the browser artifact identity and their checksums.
It opens `NEX-P4-12` for final acceptance of the local Phase 4 experience.

```zsh
.venv/bin/python scripts/verify_phase_four_product_acceptance.py
.venv/bin/python -m unittest discover -s tests -v
```
