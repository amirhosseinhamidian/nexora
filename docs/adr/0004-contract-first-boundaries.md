# ADR-0004 - Contract-first Cross-boundary Communication

وضعیت: **Accepted candidate for NEX-P0-02**

تاریخ: `2026-10-22`

## Context

Nexora و TRD Bot repository و release مستقل دارند. همچنین Web و Server Nexora با دو زبان متفاوت
توسعه می‌یابند. typeهای داخلی یک runtime نمی‌توانند به‌تنهایی سازگاری این مرزها را تضمین کنند.

## Decision

تمام boundaryهای cross-process و cross-product contract-first هستند:

- REST با OpenAPI نسخه‌دار؛
- Event و Export با JSON Schema و fixtureهای canonical؛
- payload دارای `schema_version`، timestamp UTC و SourceReference؛
- command قابل retry دارای `correlation_id` و `idempotency_key`؛
- schema ناشناخته یا نسخه ناسازگار fail-closed است؛
- contractها در `packages/contracts` مستقل از runtime نگهداری می‌شوند؛
- generated client قابل استفاده است، اما source contract نیست.

جزئیات endpoint، event و compatibility matrix در `NEX-P0-03` فریز خواهد شد. تا آن مرحله runtime
integration مجاز نیست.

## Consequences

- drift میان TRD Bot، Server و Web با fixture قابل تشخیص می‌شود؛
- client تولیدشده قابل بازسازی است و contract دستی موازی ایجاد نمی‌کند؛
- هر breaking change نیازمند schema version و compatibility evidence است؛
- نگهداری schema و golden fixture بخشی از هزینه پذیرفته‌شده توسعه است.
