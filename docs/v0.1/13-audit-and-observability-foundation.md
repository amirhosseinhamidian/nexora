# NEX-P1-08 — Audit and Observability Foundation

وضعیت: **Candidate — آماده‌ی Freeze پس از CI سبز**

این مرحله `NEX-P1-GAP-004` را می‌بندد و روی Freeze معتبر `NEX-P1-07` با commit
`6ff8e4f185a51fec0fa2c9a7353d35897fef7eec` بنا شده است.

## Logging امن

هر event با schema نسخه‌دار، UTC، level، service، نام event و reason code به JSON
Lines تبدیل می‌شود. requestها فقط method، route template، status، duration و
correlation ID را ثبت می‌کنند. query string و body ثبت نمی‌شوند. Bearer token،
cookie، secret، password، recovery code، CSRF و credential در ساختارهای تو در تو
redact می‌شوند و raw exception message نیز وارد log نمی‌شود.

در production متغیر `NEXORA_LOG_FILE` اجباری است. مسیر باید absolute باشد، symlink
پذیرفته نمی‌شود و handler با سقف ۱۰ MiB و ۳۰ backup فایل را rotate می‌کند.

## Metrics و readiness

`RuntimeMetrics` یک snapshot محدود و thread-safe برای این موارد نگه می‌دارد:

- تعداد request بر اساس method، route template و status class
- histogram زمان پاسخ با bucketهای ثابت
- cycle، claimed، succeeded و failed برای Worker
- size، checked-in، checked-out و overflow برای pool دیتابیس

هیچ owner، session، raw path، query یا payload به label تبدیل نمی‌شود. endpoint عمومی
metrics وجود ندارد و route dimension حداکثر ۶۴ مقدار مستقل دارد. `/health/ready`
قرارداد `nexora-readiness-v1` را برای database،
identity و TRD Bot برمی‌گرداند و target یا credential را نمایش نمی‌دهد.

## Security audit

جدول PostgreSQL موجود با trigger غیرقابل‌تغییر باقی می‌ماند. guard جدید metadata،
کلیدهای حساس و مقادیر غیر scalar را رد می‌کند و اندازه را به ۴ KiB محدود می‌سازد.
retention امنیتی ۴۰۰ روز و retention metricهای exportشده ۹۰ روز مطابق سیاست P0-04
است؛ اجرای retention و archival در `NEX-P1-12` انجام می‌شود.

## مرز مرحله

این مرحله collector خارجی، public metrics، tracing توزیع‌شده، dashboard کامل، SaaS،
multi-user، exchange credential، wallet، live execution یا autonomous AI اضافه
نمی‌کند. پس از Freeze فقط `NEX-P1-09 — TRD Bot Sync Runtime` باز می‌شود.

## اجرای گیت‌ها

```bash
uv run python scripts/verify_audit_observability.py
uv run python -m unittest discover -s tests -v
uv run ruff format --check apps/server alembic scripts/verify_audit_observability.py tests/test_audit_observability.py
uv run ruff check apps/server alembic scripts/verify_audit_observability.py tests/test_audit_observability.py
uv run mypy
uv run pytest -m "not integration" -q
```
