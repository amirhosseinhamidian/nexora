# ADR 0021 — Runtime API, authentication lifecycle and contract toolchain

Status: Candidate for NEX-P1-07

## Context

Freeze مرحله‌ی roadmap reconciliation سه Gap را به P1-07 سپرد: metadata و error
envelope و correlation در API، ابزار deterministic قراردادها، و چرخه‌ی HTTP
هویت شامل recent reauthentication. هسته‌ی P1-06 سرویس و persistence را داشت،
اما سطح HTTP کامل و evidence پایدار reauthentication را نداشت.

## Decision

- تمام پاسخ‌های API دارای `X-Correlation-ID` هستند و خطاهای API با
  `nexora-error-envelope-v1` برگردانده می‌شوند.
- `/version` نسخه، commit SHA و fingerprint پیکربندی را منتشر می‌کند؛ مقدار
  production commit از `SOURCE_COMMIT_SHA` گرفته می‌شود و secret نیست.
- endpointهای passkey برای bootstrap، authentication، registration، recovery،
  session rotation، reauthentication و revocation صریح و same-origin هستند.
- recent reauthentication با ستون durable `reauthenticated_at` و پنجره‌ی
  ۳۰۰ثانیه‌ای enforce می‌شود.
- مدل‌های Pydantic منبع قراردادند. JSON Schema، OpenAPI snapshot، manifest
  پایتون و TypeScript typeها به‌صورت deterministic تولید و با `--check` کنترل
  می‌شوند.

## Consequences

Frontend فازهای بعد می‌تواند بدون تعریف دستی type به API متصل شود. تغییر مدل یا
route بدون بازتولید artifactها CI را fail می‌کند. هیچ password، self-registration،
حساب دوم، credential صرافی، wallet یا live execution اضافه نمی‌شود.
