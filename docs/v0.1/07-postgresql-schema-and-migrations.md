# NEX-P1-03 — PostgreSQL Schema and Migrations

وضعیت: **Frozen**
تاریخ تصمیم: ۲۰۲۶-۱۰-۲۵

## هدف

این مرحله persistence spine حداقلی Nexora را روی PostgreSQL 17 ایجاد می‌کند:
تنظیم امن connection از فایل خصوصی، مدل‌های SQLAlchemy 2، migrationهای Alembic و
اولین schema برگشت‌پذیر. اتصال runtime API/Worker، دریافت داده از TRD Bot، job،
outbox و identity هنوز فعال نمی‌شوند.

## پیش‌نیاز قطعی

`NEX-P1-02` در commit
`6ee2db690fa713a94bad016cc19f18eed6729879` Freeze شده است. checksum canonical
رکورد Freeze برابر
`6b39f61195a461d7d647cb735c038e16f8d8c98deed71c21c5af7b56027f1c3f`
است و گام مجاز بعدی را `NEX-P1-03` اعلام می‌کند.

## تنظیم امن Database

DSN مستقیم در environment، repository، log یا command line پذیرفته نمی‌شود.
Migration process فقط path یک فایل خصوصی مطلق را از متغیر
`NEXORA_MIGRATION_DATABASE_DSN_FILE` می‌گیرد. symlink رد می‌شود؛ mode محیط توسعه
حداکثر `0600` و mode production دقیقاً `0400` است. driver فقط
`postgresql+psycopg` است و password در representation یا error نمایش داده نمی‌شود.

این متغیر فقط متعلق به ابزار migration است و به allowlist تنظیمات runtime
P1-02 اضافه نشده؛ بنابراین API و Worker همچنان بدون database side effect بالا
می‌آیند و unknown runtime configuration را fail-closed رد می‌کنند.

## Schema اولیه

namespace اختصاصی `nexora` و revision اولیه `20261025_0001` شامل این جدول‌هاست:

| جدول | مسئولیت | invariant اصلی |
| --- | --- | --- |
| `owner_profiles` | ریشه داده تک‌مالک | فقط کلید `primary_owner` |
| `source_references` | lineage نسخه‌دار منبع | owner، schema/source version، correlation ID و SHA-256 الزامی |
| `immutable_source_evidence` | payload اصلی JSONB | object معتبر، checksum منطبق و یک evidence برای هر source reference |

دو جدول منبع در سطح PostgreSQL با trigger از UPDATE و DELETE محافظت می‌شوند.
تمام timestampها timezone-aware هستند و connection timezone روی UTC قرار می‌گیرد.
`search_path` هر connection صراحتاً `public` است و جدول نسخه Alembic نیز در
`public.alembic_version` نگهداری می‌شود. در نتیجه حتی اگر نام role پایگاه داده
با schema برنامه (`nexora`) یکسان باشد، reflection و drift check پایدار می‌مانند.
جدول داخلی `alembic_version` صراحتاً از inventory مربوط به autogenerate کنار
گذاشته می‌شود و هیچ جدول برنامه‌ای با این فیلتر نادیده گرفته نمی‌شود.

## Migration lifecycle

```bash
export NEXORA_MIGRATION_DATABASE_DSN_FILE=/absolute/private/path/nexora-database.dsn
uv run alembic upgrade head
uv run pytest apps/server/tests/test_postgresql_integration.py -m integration -q
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
```

application startup هیچ `create_all` یا migration خودکاری اجرا نمی‌کند. migration
فقط یک عملیات صریح operator/CI است و تا Freeze نسخه upgrade و downgrade الزامی‌اند.

## Local PostgreSQL

فایل `infra/compose/postgresql.dev.yml` فقط PostgreSQL توسعه را روی loopback و
پورت پیش‌فرض `55432` در دسترس می‌گذارد. password از فایل خارج repository به
Docker secret تزریق می‌شود. این compose ادعای private production readiness ندارد.

## موارد عمداً deferred

- projection checkpoint و adapter اجرایی TRD Bot: `NEX-P1-04`؛
- durable jobs، lease، retry و transactional outbox: `NEX-P1-05`؛
- WebAuthn credential، session و service token: `NEX-P1-06`؛
- Portfolio، Journal و Export domain schema: فازهای دامنه مربوطه؛
- live order، exchange credential، wallet و multi-tenant identity: خارج از v0.1.

## معیار پذیرش

```bash
python3 scripts/verify_application_composition.py
python3 scripts/verify_postgresql_schema.py
python3 -m unittest discover -s tests -v
uv run ruff format --check apps/server alembic
uv run ruff check apps/server alembic
uv run mypy
uv run pytest -m "not integration" -q
```

```text
NEX_P1_02_PREREQUISITE=PASS
NEX_P1_03_POSTGRESQL_SCHEMA=PASS
```

## شواهد Freeze

Candidate نهایی با SHA
`a448c996acdbee33bba88e788d7f768a6a96b5f9` و پیام commit
`fix(nexora): isolate PostgreSQL integration tests in CI` پذیرفته شد. Workflow
اصلی PostgreSQL با run `40204544416` هر سه job قرارداد، backend و PostgreSQL 17
را سبز کرد. runهای رگرسیون `40204544421`، `40204544423` و `40204544462` نیز
Runtime Foundation، قراردادهای Phase 0 و Application Composition را روی همان
SHA تأیید کردند.

```text
NEX_P1_02_PREREQUISITE=PASS
NEX_P1_03_POSTGRESQL_SCHEMA=PASS
NEX_P1_03_FREEZE=PASS
```

مرحله مجاز بعدی `NEX-P1-04 — Versioned TRD Bot Adapter` است.
