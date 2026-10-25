# NEX-P1-02 — Application Composition and Typed Runtime Configuration

وضعیت: **Candidate — Ready for Freeze**
تاریخ تصمیم: ۲۰۲۶-۱۰-۲۵

## هدف

این مرحله تنظیمات ضمنی و hard-coded مرحله Bootstrap را به یک مرز type-safe،
immutable و fail-closed تبدیل می‌کند و API و Worker را از یک composition factory
مشترک می‌سازد. هنوز database، authentication، اتصال اجرایی TRD Bot، durable job
یا production deployment تحویل داده نمی‌شود.

## پیش‌نیاز قطعی

`NEX-P1-01` در commit
`618907b0bc9c5f57e2e72f8d2c666a7f5b6b3266` Freeze شده است. checksum canonical
رکورد Freeze برابر
`9daa50079de7a0288c877f967ee91c3393e7de157f2bf40f66d9555be237efc0`
است. هر drift در این رکورد مانع پذیرش P1-02 می‌شود.

## قرارداد Configuration

فقط متغیرهای غیرمحرمانه زیر پذیرفته می‌شوند:

| متغیر | پیش‌فرض | محدودیت |
| --- | --- | --- |
| `NEXORA_ENVIRONMENT` | `development` | `development`، `test` یا `production` |
| `NEXORA_DEPLOYMENT_PROFILE` | `local_development` | فقط local یا private single-host |
| `NEXORA_LOG_LEVEL` | `INFO` | `DEBUG` در production ممنوع |
| `NEXORA_DEFAULT_LOCALE` | `fa` | `fa` یا `en` |
| `NEXORA_DEFAULT_THEME` | `system` | `light`، `dark` یا `system` |
| `NEXORA_API_HOST` | `127.0.0.1` | local فقط loopback؛ private داخل topology ثبت‌شده |
| `NEXORA_API_PORT` | `8000` | بازه ۱۰۲۴ تا ۶۵۵۳۵ |

هر متغیر ناشناخته با پیشوند `NEXORA_`، مقدار خالی یا ترکیب ناامن باعث توقف startup
می‌شود. dotenv به‌صورت خودکار خوانده نمی‌شود و هیچ secret، database URL، service
token یا credential در این schema وجود ندارد.

## Composition

- `RuntimeSettings` مدل immutable تنظیمات است.
- `compose_application` تنها factory مشترک API و Worker است.
- `ApplicationContainer` فقط settings و runtime identity غیرمحرمانه دارد.
- fingerprint قطعی با SHA-256 روی schema و canonical JSON محاسبه می‌شود.
- fingerprint تنظیمات پیش‌فرض برابر
  `5d4f9f7b6a1b7e1d8ab7af749136afff0b9e4de419d05f34a47497e68818ea04` است.
- API همچنان فقط liveness عمومی مرحله Bootstrap را دارد.
- Worker فقط `--check` را اجرا می‌کند و هیچ jobای claim نمی‌کند.
- هیچ global service locator یا adapter زودهنگام ساخته نمی‌شود.

## مرز امنیتی

پروفایل `public_internet`، live order، exchange credential، wallet، دسترسی مستقیم
به دیتابیس TRD Bot، autonomous AI execution و multi-tenant identity همچنان ممنوع‌اند.
production فقط با `private_single_host` شناخته می‌شود، اما استقرار production تا
`NEX-P1-06` آماده یا ادعا نمی‌شود.

## معیار پذیرش

```bash
python3 scripts/verify_runtime_foundation.py
python3 scripts/verify_application_composition.py
python3 -m unittest discover -s tests -v
uv sync --frozen --python 3.13
uv run ruff format --check apps/server
uv run ruff check apps/server
uv run mypy
uv run pytest -q
```

```text
NEX_P1_01_PREREQUISITE=PASS
NEX_P1_02_APPLICATION_COMPOSITION=PASS
```

مرحله بعد فقط `NEX-P1-02-FREEZE` است؛ پس از Freeze، ورود به
`NEX-P1-03 — PostgreSQL Schema and Migrations` مجاز می‌شود.
