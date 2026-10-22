# ADR-0002 - Next.js Web and FastAPI Server

وضعیت: **Accepted and frozen by NEX-P0-02**

تاریخ: `2026-10-22`

## Context

Nexora به رابط داده‌محور، دسترس‌پذیر و دو‌زبانه نیاز دارد. Backend نیز باید sync، job، Export،
PostgreSQL و در نسخه‌های بعدی AI/ML را بدون انتقال منطق تخصصی به Frontend پشتیبانی کند.

## Decision

Web روی Node.js `24.x LTS`، Next.js `16.x` App Router، React `19.x` و TypeScript `5.x` strict ساخته
می‌شود. pnpm `10.x` package manager و Tailwind CSS 4 به‌همراه Radix UI پایه طراحی هستند.

Server روی Python `3.13.x` و FastAPI ساخته می‌شود و از Pydantic 2، SQLAlchemy 2، Alembic 1 و
psycopg 3 استفاده می‌کند. dependency و lockfileهای Python با `uv` مدیریت می‌شوند.

FastAPI مالک command، validation دامنه، persistence، Integration و Export orchestration است. Next.js
Route Handler فقط در صورت نیاز می‌تواند نقش same-origin transport/session adapter داشته باشد؛ منطق
دامنه، دسترسی مستقیم PostgreSQL و source-of-truth state در Web ممنوع است.

Exact dependency versions در `NEX-P1-01` پس از bootstrap در lockfileها ثبت می‌شوند. Phase 0 فقط
release lineها را فریز می‌کند تا patchهای امنیتی بدون ADR جدید قابل دریافت باشند.

## Consequences

- Frontend و API مستقل تست و build می‌شوند.
- JSON Schema و OpenAPI مرز مشترک هستند؛ TypeScript type به‌تنهایی contract خارجی نیست.
- Python مسیر طبیعی برای Export و ML آینده فراهم می‌کند، بدون فعال‌کردن ML در v0.1.
- دو runtime باید در development و CI پشتیبانی شوند.

## Rejected alternatives

- NestJS server: انتخاب معتبری است، اما هم‌راستایی FastAPI با TRD Bot، pipelineهای داده و ML آینده
  برای این محصول ارزش بیشتری دارد.
- Next.js-only backend: durable worker و domain isolation را ضعیف می‌کند.
- Python `3.15.x`: در تاریخ تصمیم بسیار تازه است؛ `3.13.x` baseline محافظه‌کارانه‌تر و پایدارتر است.
