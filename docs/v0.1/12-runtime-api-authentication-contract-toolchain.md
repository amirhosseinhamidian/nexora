# NEX-P1-07 — Runtime API, Authentication Lifecycle & Contract Toolchain

وضعیت: **Frozen**

این مرحله سه Gap ثبت‌شده در Freeze رودمپ را می‌بندد:

- `NEX-P1-GAP-001`: metadata، error envelope و correlation سراسری API
- `NEX-P1-GAP-002`: toolchain قطعی Python/TypeScript/OpenAPI/JSON Schema
- `NEX-P1-GAP-003`: چرخه‌ی HTTP passkey، session و recent reauthentication

## API و lifecycle

`/version` اطلاعات build و configuration را منتشر می‌کند. تمام پاسخ‌ها
`X-Correlation-ID` دارند و خطاها از schema نسخه‌دار
`nexora-error-envelope-v1` استفاده می‌کنند. endpointهای `/v1/auth/*` چرخه‌ی
bootstrap محلی، ورود passkey، مشاهده و rotation نشست، reauthentication، افزودن
passkey، recovery، logout و revoke-all را پوشش می‌دهند.

Cookie همچنان `__Host-nexora_session` با `Secure`، `HttpOnly` و
`SameSite=Strict` است. mutationها Origin دقیق، JSON و CSRF معتبر می‌خواهند.
برای عملیات حساس، evidence ستون `reauthenticated_at` باید حداکثر ۳۰۰ ثانیه
قدمت داشته باشد.

## Contract toolchain

مدل‌های Pydantic در `runtime_contracts.py` منبع canonical هستند. generator این
خروجی‌ها را ایجاد می‌کند:

- OpenAPI snapshot
- JSON Schemaهای بسته
- fixtureهای معتبر
- manifest پایتون
- typeهای TypeScript

اجرای بدون drift:

```bash
uv run python scripts/generate_runtime_contracts.py --check
```

## Freeze evidence

Candidate نهایی `2a40a03e5a7995e6b845b3ce73e62646449da507` است. اجرای اصلی
`40372395158` هر چهار job قرارداد cross-language، قرارداد runtime، backend و
PostgreSQL 17 را سبز کرد و هشت workflow رگرسیون نیز روی همان SHA موفق شدند.
رکورد immutable این پذیرش در
`artifacts/p1-07/runtime-api-auth-freeze.json` قرار دارد.

`NEX-P1-07` اکنون Frozen است و فقط `NEX-P1-08` را باز می‌کند.
