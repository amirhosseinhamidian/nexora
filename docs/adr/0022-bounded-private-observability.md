# ADR 0022 — Bounded private observability

Status: Frozen by NEX-P1-08

## Context

هسته‌ی قبلی correlation ID و security audit immutable داشت، اما logging ساختاریافته،
metrics محدود، readiness وابسته‌محور و سیاست rotation اجرایی نداشت. استفاده از
collector خارجی یا stack سنگین telemetry برای نسخه‌ی single-host شخصی ضروری نیست.

## Decision

- رخدادهای runtime فقط به‌شکل JSON Lines با زمان UTC، event و reason code ثبت می‌شوند.
- query string، body، raw exception message، token، cookie و recovery code وارد log
  نمی‌شوند؛ redaction بازگشتی آخرین سد دفاعی است.
- metricها در v0.1 snapshot محدود درون‌پردازه‌ای هستند و labelها فقط method، route
  template و status class را می‌پذیرند.
- `/health/ready` وضعیت database، identity و TRD Bot adapter را بدون انتشار target،
  DSN یا credential اعلام می‌کند و در صورت نقص fail closed است.
- log production در فایل محلی خصوصی با rotation حجمی ۱۰ MiB و ۳۰ نسخه نگهداری
  می‌شود. retention عملیاتی نهایی در NEX-P1-12 اجرا خواهد شد.
- security audit موجود همچنان PostgreSQL append-only است؛ metadata قبل از persistence
  از نظر کلید حساس، نوع و اندازه اعتبارسنجی می‌شود.

## Consequences

API و Worker evidence قابل‌همبستگی و metricهای کم‌کاردینال تولید می‌کنند، بدون اینکه
secret یا داده‌ی مالی در telemetry کپی شود. endpoint عمومی metrics و ارسال telemetry
به سرویس ثالث اضافه نشده است. persistence تاریخی metric و dashboard کامل به مراحل
بعدی تعلق دارند.
