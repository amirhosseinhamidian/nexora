# NEX-P1-04 — Versioned TRD Bot Adapter

وضعیت: **Candidate**
تاریخ تصمیم: ۲۰۲۶-۱۰-۲۵

## هدف

این مرحله adapter نسخه‌دار و fail-closed میان Nexora و TRD Bot را پیاده می‌کند.
ارتباط فقط از API رسمی `/api/v1/integration/nexora` انجام می‌شود؛ دسترسی مستقیم
به database، credential صرافی، wallet و ارسال سفارش زنده همچنان ممنوع است.

## پیش‌نیاز قطعی

`NEX-P1-03` در commit
`519c193d911ff8b0e609c3b9be244a8034231c84` Freeze شده و checksum canonical
رکورد آن
`0ef07cebdf42eea58f8014ad19ade51cd998d61e7dd1e2ba7d04330962eb3256`
است. این رکورد فقط `NEX-P1-04` را باز می‌کند.

## قرارداد سازگاری

TRD Bot `0.3.0` عمداً `legacy_read_only_blocked` می‌ماند. تنها نسخه‌های
`>=0.3.1,<0.4.0` و فقط پس از تطبیق دقیق قابلیت‌های contract، event envelope،
export manifest، source reference و سه command مربوط به review پذیرفته می‌شوند.
نسخه یا schema ناشناخته fail-closed است.

adapter هر هشت عملیات frozen را پوشش می‌دهد: capability، snapshot، event feed،
event lookup، decision review، ایجاد export، وضعیت export و manifest آن. تمام
پاسخ‌ها با مدل‌های strict و immutable بررسی می‌شوند. checksum event، timestamp
UTC، cursor و completeness manifest نیز پیش از خروج داده از boundary اعتبارسنجی
می‌شوند.

## تنظیم امن

تنها مسیر فایل‌های خصوصی از این دو متغیر خوانده می‌شود:

- `NEXORA_TRD_BOT_BASE_URL_FILE`
- `NEXORA_TRD_BOT_TOKEN_FILE`

هر فایل باید absolute، regular و بدون symlink باشد. محیط production دقیقاً mode
`0400` و HTTPS می‌خواهد. در development فایل owner-only تا `0600` و HTTP فقط
برای loopback مجاز است. token در browser، export، log یا fixture قرار نمی‌گیرد.

## Failure و retry

قبل از negotiation هیچ sync operation اجرا نمی‌شود. فقط 429، 502، 503 و 504 تا
چهار attempt با full jitter بین 250 تا 4000 میلی‌ثانیه retry می‌شوند. POST بدون
idempotency key پذیرفته نمی‌شود. پاسخ 410 به full snapshot resync و 412 به پاک
شدن negotiation و الزام مذاکره دوباره منجر می‌شود. delivery همچنان
at-least-once است و هیچ ادعای exactly-once وجود ندارد.

## مرز اجرایی

در P1-04 client ساخته شده اما در composition مربوط به API یا Worker ثبت نشده
است؛ بنابراین startup هیچ network side effect ندارد. همچنین چون provider سازگار
TRD Bot 0.3.1 هنوز به‌عنوان dependency عملیاتی این repository عرضه نشده، تست‌ها
با `httpx.MockTransport` انجام می‌شوند و live-provider smoke ادعا نمی‌شود.
durable poll، checkpoint، projection و outbox به `NEX-P1-05` تعلق دارند.

## معیار پذیرش

```bash
python3 scripts/verify_postgresql_schema.py
python3 scripts/verify_trd_bot_adapter.py
python3 -m unittest discover -s tests -v
uv run ruff format --check apps/server
uv run ruff check apps/server
uv run mypy
uv run pytest -m "not integration" -q
```

```text
NEX_P1_03_PREREQUISITE=PASS
NEX_P1_04_TRD_BOT_ADAPTER=PASS
```

مرحله مجاز بعدی فقط `NEX-P1-04-FREEZE` است و پس از Freeze،
`NEX-P1-05 — Durable Jobs, Checkpoints and Transactional Outbox` باز می‌شود.
