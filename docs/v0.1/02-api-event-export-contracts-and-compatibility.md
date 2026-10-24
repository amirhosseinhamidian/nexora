# NEX-P0-03 — قراردادهای API، Event، Export و سازگاری

وضعیت: **Frozen**

تاریخ تصمیم: `2026-10-22`

پیش‌نیاز: `NEX-P0-02` در وضعیت Frozen

گام مجاز بعدی: `NEX-P0-04`

## هدف

این مرحله مرز قابل‌اعتماد میان Nexora `0.1.x` و TRD Bot را پیش از ساخت runtime
تعریف می‌کند. خروجی آن قرارداد، schema، fixture و تست است؛ endpoint واقعی،
database، authentication و deployment در این مرحله ساخته نمی‌شوند.

اصل مرکزی این است که Nexora یک محصول مستقل است: داده‌های TRD Bot را فقط از
مرز نسخه‌دار دریافت می‌کند، در PostgreSQL خودش projection می‌سازد و هیچ‌وقت
جدول‌های داخلی TRD Bot را مستقیم نمی‌خواند.

## نتیجه بررسی TRD Bot 0.3.0

کد نسخه نهایی `0.3.0` بررسی شد. endpointهای خواندنی برای health، market
context، decision evaluation، candidate lineage، risk، portfolio intelligence،
alert/outcome و monitoring وجود دارند. با این حال چهار شکاف blocking باقی است:

1. namespace و capabilities مشترک برای Nexora وجود ندارد؛
2. event feed بیرونی و cursor-based وجود ندارد؛
3. export عمومی و نسخه‌دار در قالب JSON/JSONL/CSV/Parquet/ZIP وجود ندارد؛
4. command اختصاصی و idempotent برای review تصمیم‌های Paper/Shadow وجود ندارد.

بنابراین `0.3.0` در ماتریس سازگاری `legacy_read_only_blocked` است. راه‌حل، یک
تغییر additive در TRD Bot `0.3.1+` است؛ direct database fallback مجاز نیست.
inventory دقیق endpointها در
[`trd-bot-v0.3.0-inventory.json`](../../contracts/integration/v1/trd-bot-v0.3.0-inventory.json)
ثبت شده است.

## قرارداد REST نسخه اول

namespace ثابت قرارداد:

```text
/api/v1/integration/nexora
```

| متد | مسیر | کاربرد |
|---|---|---|
| GET | `/capabilities` | مذاکره نسخه و قابلیت‌ها |
| GET | `/snapshots/{resource_type}` | bootstrap و backfill پایدار |
| GET | `/events` | دریافت incremental با cursor |
| GET | `/events/{event_id}` | بازیابی event واحد |
| POST | `/commands/decision-reviews` | accept/reject/defer فقط برای Paper/Shadow |
| POST | `/exports` | ایجاد export پایدار و idempotent |
| GET | `/exports/{export_id}` | وضعیت export |
| GET | `/exports/{export_id}/manifest` | manifest فقط برای export کامل |

هر request دارای `Accept` و `X-Correlation-ID` است. هر POST علاوه بر
`Content-Type` به `Idempotency-Key` نیاز دارد. پاسخ‌ها نسخه TRD Bot، نسخه
قرارداد و correlation ID را اعلام می‌کنند. snapshot و event payload همیشه
schema version و source reference دارند.

OpenAPI مرجع در
[`openapi.json`](../../contracts/integration/v1/openapi.json) قرار دارد.

## قابلیت‌سنجی و ماتریس سازگاری

Nexora پیش از sync، `/capabilities` را می‌خواند و contract، envelope، manifest،
source reference و commandهای لازم را تطبیق می‌دهد. نتیجه‌ها:

| TRD Bot | وضعیت | رفتار Nexora |
|---|---|---|
| `<0.3.0` | unsupported | fail closed |
| `0.3.0` | legacy read-only blocked | نمایش ناسازگاری و عدم sync |
| `>=0.3.1,<0.4.0` | compatible if capabilities match | مذاکره و سپس sync |
| `>=0.4.0` | unknown | fail closed تا ثبت compatibility جدید |

HTTP `412` قابلیت‌سنجی مجدد را اجباری می‌کند. schema ناشناخته پذیرفته یا
حدس زده نمی‌شود.

## Event feed

تحویل eventها `at_least_once` است و نه exactly-once. ترتیب فقط در محدوده هر
aggregate تضمین می‌شود. envelope شامل این شواهد است:

- شناسه event، نوع و نسخه schema؛
- زمان رخداد و انتشار در UTC؛
- source reference دارای checksum؛
- aggregate type/id/version؛
- correlation، causation و idempotency؛
- schema و SHA-256 محتوای payload.

Nexora با `event_id` و `idempotency_key` duplicate را حذف می‌کند. پرش نسخه
aggregate باعث توقف projection و backfill می‌شود. cursor منقضی با HTTP `410`
پاسخ داده می‌شود و تنها رفتار مجاز، full snapshot resync است؛ reset خاموش cursor
ممنوع است.

## Commandهای محدود

تنها commandهای نسخه اول عبارت‌اند از:

- `decision_review.accept.v1`
- `decision_review.reject.v1`
- `decision_review.defer.v1`

این commandها صرفاً review انسانی/سیستمی روی تصمیم‌های `paper` یا `shadow`
هستند. ارسال، لغو یا اصلاح سفارش، حساب صرافی، credential، کیف پول و انتقال وجه
خارج از قرارداد است. timeout پس از POST ابتدا با idempotency key lookup بررسی
می‌شود و سپس retry صورت می‌گیرد.

## Retry و failure semantics

GETها safe هستند. POST فقط با idempotency key قابل retry است. حداکثر چهار تلاش
با full jitter از `250ms` تا `4000ms` انجام می‌شود و `Retry-After` رعایت می‌شود.
فقط `429/502/503/504` retryable هستند.

- checksum نامعتبر: reject و alert؛
- payload ناشناخته: quarantine و degrade؛
- event gap: توقف projection و backfill؛
- cursor منقضی: full snapshot resync؛
- منبع موقتاً unavailable: آخرین snapshot تأییدشده با علامت stale؛
- idempotency conflict: reject بدون replay؛
- export ناقص: unsuccessful و غیرقابل مصرف.

error envelope نسخه‌دار است و هیچ secret یا stack trace داخلی را حمل نمی‌کند.

## Export برای portability و تحلیل AI

حالت‌های `full`، `incremental` و `selected` و فرمت‌های JSON، JSONL، CSV،
Parquet و ZIP تعریف شده‌اند. هر export موفق manifest دارد که این موارد را ثبت
می‌کند:

- نسخه منبع و قرارداد؛
- scope، filter و بازه زمانی؛
- timezone برابر UTC؛
- currency و unit context؛
- lineage references؛
- schema، تعداد ردیف، اندازه و SHA-256 هر فایل؛
- redaction profile و وضعیت `complete`.

دو profile وجود دارد: `private` و `ai_safe`. هیچ‌کدام اجازه export کردن secret،
credential یا کلید رمزنگاری را ندارند. JSON canonical بر اساس RFC 8785 تعریف
شده تا checksum و مقایسه deterministic باشد.

## artifactهای قرارداد

- `contracts/integration/v1/integration-contract.json`
- `contracts/integration/v1/compatibility-matrix.json`
- `contracts/integration/v1/openapi.json`
- `contracts/integration/v1/schemas/*.schema.json`
- `contracts/integration/v1/fixtures/*.json`
- ADRهای `0005` تا `0007`

fixtureها نمونه golden برای capabilities، event، decision review، receipt،
export manifest و خطای ناسازگاری هستند. verifier هم drift قرارداد، endpoint،
schema، fixture، security boundary و freeze پیش‌نیاز را کنترل می‌کند.

## مرز امنیتی این مرحله

این مرحله mechanism احراز هویت یا TLS/deployment topology را انتخاب نمی‌کند؛
این تصمیم متعلق به `NEX-P0-04` است. تا آن زمان هیچ runtime integration مجاز
نیست. موارد زیر صریحاً ممنوع‌اند:

- direct TRD Bot database access؛
- unversioned payload acceptance؛
- retry کردن POST بدون idempotency؛
- پذیرش export ناقص؛
- secret-bearing export؛
- live-order، wallet، transfer و exchange credential command.

## تحویل لازم به TRD Bot

پیش از شروع integration runtime در Nexora، یک مرحله مستقل در repository ربات
باید قرارداد v1 را به‌صورت additive روی `0.3.1+` پیاده‌سازی، تست و freeze کند.
وجود endpointهای داخلی `0.3.0` به‌تنهایی acceptance محسوب نمی‌شود.

## معیار پذیرش NEX-P0-03

- Freeze مرحله `NEX-P0-02` معتبر باشد؛
- مجموعه endpointها و operation IDها دقیقاً با OpenAPI برابر باشد؛
- ماتریس سازگاری `0.3.0` را compatible اعلام نکند؛
- event delivery، cursor expiry، gap detection و deduplication صریح باشند؛
- POST بدون idempotency غیرمجاز باشد؛
- schemaها بسته و fixtureها deterministic و بدون secret باشند؛
- export ناقص پذیرفته نشود؛
- direct DB و تمام قابلیت‌های اجرای واقعی ممنوع بمانند؛
- همه verifierها و unit testها سبز باشند.

دستورهای بررسی:

```bash
python3 scripts/verify_scope_contract.py
python3 scripts/verify_technical_baseline.py
python3 scripts/verify_integration_contracts.py
python3 -m unittest discover -s tests -v
```

خروجی مورد انتظار این مرحله:

```text
NEX_P0_03_INTEGRATION_CONTRACT=PASS
```

## Freeze evidence

Candidate این مرحله با commit و اجرای CI همسان زیر پذیرفته و فریز شد:

| شاهد | مقدار |
| --- | --- |
| repository | `amirhosseinhamidian/nexora` |
| candidate commit | `c15ff7a0d6010d11c8536790d7dd50d0a2eb9fb1` |
| commit message | `docs(nexora): establish P0-03 integration contracts` |
| branch | `feature/v0.1-foundation` |
| GitHub Actions run | `https://github.com/amirhosseinhamidian/nexora/actions/runs/40077691014` |
| required jobs | `scope-contract`، `technical-baseline` و `integration-contract` |
| conclusion | `success` برای هر سه job |
| Integration Contract checksum | `435e96fc928b71c5c98ebcb6f4e41a928f9f32e073c30ab567246f52c6d78c88` |
| Technical Baseline checksum | `fba77f5f95c0dcaa59db9d5ed0b0e95290066a90a50d79f97a102375ddde69d3` |
| Scope Contract checksum | `9ca6c10fb916861bab9a3e8facf7f24e5a84855e97a1f689a48954625377217c` |

GitHub در همین run تمام verifierها و `53` تست contract را با نتیجه موفق اجرا
کرده است. Freeze Record ماشین‌خوان در
[`artifacts/p0-03/integration-contract-freeze.json`](../../artifacts/p0-03/integration-contract-freeze.json)
نگهداری می‌شود.

خروجی verifier پس از Freeze باید شامل marker زیر باشد:

```text
NEX_P0_03_FREEZE=PASS
```

گام مجاز بعدی فقط `NEX-P0-04 — Security, Identity and Private Deployment Boundary`
است. همچنان تا Freeze نهایی Phase 0 هیچ runtime integration یا bootstrap مجاز
نیست.
