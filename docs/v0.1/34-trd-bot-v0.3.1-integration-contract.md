# NEX-P3-02 — TRD Bot v0.3.1 Integration Contract

وضعیت: **Frozen**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۴

## نتیجه

این مرحله boundary قابل‌پیاده‌سازی میان Nexora `0.1.x` و TRD Bot `0.3.1` را
فریز می‌کند. قرارداد پایه‌ی `NEX-P0-03` تغییر نکرده است؛ profile جدید، جزئیات
لازم برای پیاده‌سازی provider، احراز هویت service-to-service، resync و smoke واقعی
را روی همان `nexora-trd-integration-v1` قطعی می‌کند.

این مرحله runtime جدید، migration، table یا provider سازگار تحویل نمی‌دهد. TRD Bot
`0.3.0` در commit
`bbb9fd4fbc25e25aa512a9fde1dda912321cdd33` بررسی شده و همچنان
`legacy_read_only_blocked` است؛ بنابراین Nexora نباید با آن negotiation یا sync کند.

## API و capability negotiation

namespace یکتا `/api/v1/integration/nexora` و هشت عملیات زیر ثابت می‌مانند:

- capabilities؛
- snapshot صفحه‌بندی‌شده؛
- event feed و event lookup؛
- command مربوط به decision review؛
- ایجاد export، وضعیت export و manifest.

هر پاسخ موفق باید `X-Correlation-ID`، `X-TRD-Bot-Version` و
`X-Contract-Version` داشته باشد. فقط provider در بازه‌ی `>=0.3.1,<0.4.0` و آن هم
پس از تطبیق دقیق capabilityها پذیرفته می‌شود. نسخه، schema یا capability ناشناخته
fail-closed است و تغییر نسخه‌ی provider negotiation قبلی را باطل می‌کند.

## service-to-service authentication

تمام endpointهای integration با service token در header استاندارد
`Authorization: Bearer …` محافظت می‌شوند. token حداقل ۳۲ بایت entropy دارد، در هر
دو سرویس از فایل خصوصی absolute خوانده می‌شود و مقایسه‌ی آن constant-time است.
token در query parameter، cookie، browser، log، fixture یا export قرار نمی‌گیرد.
production فقط HTTPS و development HTTP فقط روی loopback مجاز است. نبودن یا
نامعتبر بودن credential برابر 401 و scope ناکافی برابر 403 است.

## snapshot، event و resync

snapshotها به سه گروه کامل تقسیم می‌شوند:

| گروه | resourceها |
| --- | --- |
| Portfolio | `paper_shadow_portfolio`، `paper_shadow_position`، `portfolio_intelligence`، `simulation_outcome` |
| Decision | `market_context`، `decision_evaluation`، `candidate`، `risk_gate` |
| Alert | `alert`، `alert_outcome` |

اولین page بدون cursor یک scan پایدار می‌سازد و تمام continuation pageها باید همان
مرز snapshot و ترتیب deterministic را حفظ کنند. هر item دارای source reference
نسخه‌دار و checksum است. cursor opaque است، credential ندارد و انقضای آن با 410
اعلام می‌شود؛ reset خاموش ممنوع است.

event delivery حداقل یک‌بار است، نه exactly-once. `event_id` و `idempotency_key`
برای deduplication و `aggregate.version` برای ترتیب و کشف gap استفاده می‌شوند.
schema ناشناخته quarantine، checksum اشتباه reject و gap موجب توقف انتشار
projection می‌شود.

full resync انتشار projection را متوقف می‌کند، هر سه گروه snapshot را کامل
می‌خواند، lineage و checksumها را بررسی می‌کند، eventهای موجود را با deduplication
replay می‌کند، پیوستگی aggregate version را می‌سنجد و در پایان projection و
checkpoint را atomically منتشر می‌کند. نتیجه‌ی ناقص publish نمی‌شود و gap حل‌نشده
به operator ارجاع می‌شود.

## decision review و export

commandهای `accept`، `reject` و `defer` فقط feedback برای paper/shadow هستند.
Nexora منبع حقیقت owner review باقی می‌ماند؛ command provider رکورد محلی را جایگزین
نمی‌کند، execution authorization نیست، order زنده نمی‌سازد و transaction portfolio
ثبت نمی‌کند. هر POST دارای `Idempotency-Key` است؛ replay یکسان receipt تکراری و
payload متفاوت با همان key پاسخ 409 می‌گیرد.
optimistic concurrency روی aggregate محلی owner review در Nexora و با
`expected_version` اعمال می‌شود؛ command provider به‌جای مالکیت state محلی، با
checksum همان source evidence تغییرناپذیر guard می‌شود.

export فقط با manifest کامل، checksum فایل‌ها، source lineage و profileهای
`private` یا `ai_safe` پذیرفته می‌شود. export ناقص و هرگونه secret مردود است.

## gate پیاده‌سازی

بعد از Freeze این قرارداد، پیاده‌سازی boundary باید ابتدا در repository مربوط به
TRD Bot و با release هدف `0.3.1` انجام شود. Freeze مرحله‌ی `NEX-P3-03` تا وقتی
provider واقعی تمام سناریوهای auth، capability، سه گروه snapshot، cursor replay،
410/resync، idempotency conflict و export checksum را پاس نکرده باشد مجاز نیست.
تست fixture برای توسعه کافی است، اما جای smoke واقعی را نمی‌گیرد.

نبود VPS مانع contract و local integration نیست. با این حال gate
`NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE` همچنان برقرار و deferred است و production
deployment یا release `v0.1` ادعا نمی‌شود.

## شواهد Freeze

قرارداد روی candidate زیر فریز شده است:

- commit: `c32e2d6ef923413bb159615f8f980ca52207663b`؛
- tree: `5cc823d27f768609d0bd408b2f496ec730bb3287`؛
- workflow اصلی: `TRD Bot v0.3.1 integration contract`، run
  [`41866030157`](https://github.com/amirhosseinhamidian/nexora/actions/runs/41866030157)،
  attempt 1، نتیجه `success`؛
- jobهای اصلی contract، backend regression و web regression همگی موفق؛
- هر ۳۰ workflow رگرسیون repository موفق و run/job IDهای آن‌ها در
  `artifacts/p3-02/trd-bot-v031-integration-contract-freeze.json` ثبت شده‌اند.

این Freeze فقط قرارداد و provider profile را قطعی می‌کند. هیچ migration، رفتار
runtime یا provider registration به Nexora اضافه نشده و smoke provider واقعی هنوز
انجام نشده است. در نتیجه TRD Bot `0.3.0` ناسازگار باقی می‌ماند و `NEX-P3-03`
تا ارائه‌ی provider سازگار `0.3.1` و smoke واقعی بسته است.

## معیار پذیرش Freeze

```bash
python scripts/verify_decision_review_journal_domain.py
python scripts/verify_trd_bot_v031_integration_contract.py
python -m unittest tests/test_trd_bot_v031_integration_contract.py -v
python -m unittest discover -s tests -q
python -m ruff format --check scripts/verify_trd_bot_v031_integration_contract.py tests/test_trd_bot_v031_integration_contract.py
python -m ruff check scripts/verify_trd_bot_v031_integration_contract.py tests/test_trd_bot_v031_integration_contract.py
python -m mypy
git diff --check
```

خروجی verifier باید شامل markerهای زیر باشد:

```text
NEX_P3_01_PREREQUISITE=PASS
NEX_P3_02_TRD_BOT_V031_INTEGRATION_CONTRACT=PASS
NEX_P3_02_FREEZE=PASS
NEX_P3_02_PROVIDER_IMPLEMENTATION=DEFERRED_TO_TRD_BOT
NEX_P3_03_PROVIDER_SMOKE_GATE=PRESERVED
NEX_V0_1_SERVER_DEPLOYMENT_GATE=PRESERVED_DEFERRED
```

مرحله‌ی بعد، پیاده‌سازی integration در repository مربوط به TRD Bot با release هدف
`0.3.1` است. `NEX-P3-03` تنها بعد از provider سازگار و smoke واقعی باز می‌شود.
