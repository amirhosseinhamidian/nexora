# NEX-P2-08 — TRD Bot Paper/Shadow Projection

این مرحله evidence سازگار TRD Bot را فقط برای modeهای `paper` و `shadow` به یک read model قطعی و owner-scoped تبدیل می‌کند. projection از immutable source evidence بازسازی می‌شود و منبع authoritative حسابداری، جایگزین transaction journal یا ورودی مستقیم NAV/P&L نیست.

## ورودی‌های پذیرفته‌شده

- snapshot پرتفوی با schema نسخه‌دار `trd-paper-shadow-portfolio-v1`؛
- snapshot موقعیت با schema نسخه‌دار `trd-paper-shadow-position-v1`؛
- eventهای بازشدن، به‌روزرسانی و بسته‌شدن موقعیت شبیه‌سازی‌شده؛
- provider سازگار با `nexora-trd-integration-v1` و حداقل نسخهٔ `0.3.1`.

نسخهٔ فعلی TRD Bot `0.3.0` همچنان incompatible است و runtime آن را فعال نمی‌کند. این مرحله external provider smoke یا اتصال واقعی به provider ناسازگار را ادعا نمی‌کند.

## قواعد projection

- هر evidence باید source reference، provider/schema version، زمان UTC و checksum معتبر داشته باشد.
- مقدارهای مالی فقط با decimal string پذیرفته می‌شوند؛ binary float رد می‌شود.
- mode پرتفوی و موقعیت باید یکسان و فقط `paper` یا `shadow` باشد.
- نسخهٔ aggregate موقعیت در eventها باید پیوسته باشد. gap یا conflict، آخرین state معتبر را حفظ می‌کند اما projection را `incomplete` می‌سازد.
- update یا close بدون state قبلی و هر transition پس از close رد می‌شود.
- ترتیب خروجی و checksum مستقل از ترتیب دریافت evidence است.
- schema یا payload ناشناخته بدون تولید projection قرنطینه می‌شود.

## Persistence و durable sync

جدول و migration جدیدی اضافه نشده است. read model از جدول‌های immutable موجود شامل `source_references` و `immutable_source_evidence` بازسازی می‌شود. دریافت event و snapshot همچنان از durable jobهای `trd_bot.event_sync` و `trd_bot.snapshot_sync`، checkpointهای optimistic، sync receipt و outbox استفاده می‌کند.

snapshotهای projection تعداد evidence پذیرفته و قرنطینه‌شده را در event نسخه‌دار `trd_bot.sync.projection_snapshot.completed.v1` ثبت می‌کنند. payload قرنطینه‌شده نیز به‌عنوان immutable evidence با namespace جداگانه حفظ می‌شود اما هرگز وارد read model نمی‌شود. event projection با payload نامعتبر نیز با reason code صریح `INVALID_PROJECTION_PAYLOAD` قرنطینه می‌شود.

## مرز مرحله

P2-08 هیچ endpoint عمومی، export، transaction، valuation، NAV یا P&L جدیدی ایجاد نمی‌کند. API و export به P2-09 تعلق دارند. دسترسی مستقیم به دیتابیس TRD Bot، credential صرافی، کلید یا signing کیف پول، انتقال وجه، سفارش زنده، SaaS/multi-user، اجرای خودکار AI، ML و توصیهٔ مالی یا مالیاتی همچنان ممنوع‌اند.

ورود به `NEX-P2-09` فقط بعد از Freeze مستقل P2-08 مجاز است.
