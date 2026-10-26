# NEX-P1-05 — Durable jobs, checkpoints and transactional outbox

وضعیت: **Candidate — آماده‌ی Freeze پس از CI سبز**

این مرحله لایه‌ی اجرای قابل‌بازیابی Nexora را روی PostgreSQL 17 پیاده می‌کند.
سه جدول `background_jobs`، `projection_checkpoints` و `outbox_events` در migration
`20261025_0002` اضافه شده‌اند.

## تضمین‌ها

- enqueue با idempotency key مالک‌محور انجام می‌شود و reuse با payload متفاوت رد می‌شود؛
- claim با `FOR UPDATE SKIP LOCKED`، lease زمان‌دار و batch محدود است؛
- lease منقضی قابل reclaim است و lease از‌دست‌رفته fail-closed می‌شود؛
- retry نمایی، محدود و در نهایت dead-letter است؛
- checkpoint با row version به‌صورت compare-and-swap جلو می‌رود؛
- success job، checkpoint و outbox در یک transaction ثبت می‌شوند؛
- outbox نیز lease، retry و dead-letter مستقل دارد؛
- semantics عمداً at-least-once است و ادعای exactly-once وجود ندارد.

Worker فقط job typeهایی را claim می‌کند که handler آن‌ها صریحاً inject شده باشد.
در این مرحله handler واقعی TRD Bot و credential واقعی ثبت نمی‌شود؛ این مرز مانع
دسترسی ناخواسته به شبکه یا تبدیل شدن زیرساخت به اجرای live می‌شود.

## بررسی

```bash
uv run python scripts/verify_durable_jobs_outbox.py
uv run ruff format --check apps/server alembic
uv run ruff check apps/server alembic
uv run mypy
uv run pytest -m "not integration" -q
uv run alembic upgrade head
uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
```

خروجی verifier باید شامل `NEX_P1_04_PREREQUISITE=PASS` و
`NEX_P1_05_DURABLE_JOBS_OUTBOX=PASS` باشد. مرحله بعد از Freeze، `NEX-P1-06` است.
