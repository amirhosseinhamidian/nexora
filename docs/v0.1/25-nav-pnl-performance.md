# NEX-P2-07 — NAV، P&L و Performance

این مرحله محاسبهٔ فقط‌خواندنی و owner-scoped ارزش پرتفوی را روی journal غیرقابل‌تغییر P2-04، cost basis قطعی P2-05 و شواهد قیمت/FX فریز‌شدهٔ P2-06 اضافه می‌کند. خروجی‌ها گزارش حسابداری و عملکرد فنی‌اند و توصیهٔ مالی یا مالیاتی نیستند.

## مرز محاسبه

- وضعیت holdings برای همان `as_of` از تمام تراکنش‌های `occurred_at <= as_of` بازسازی می‌شود؛ بنابراین درخواست تاریخی از snapshot فعلی holdings استفاده نمی‌کند.
- محاسبات فقط با `Decimal` انجام و تمام اعداد API به‌صورت string منتشر می‌شوند.
- هر موقعیت، evidence ID، زمان evidence، `valid_until` و source reference انتخاب‌شده را برمی‌گرداند.
- evidence منقضی‌شده حذف نمی‌شود؛ مقدار با وضعیت `stale` قابل مشاهده است.
- اگر حتی یک موقعیت فاقد valuation باشد، `nav` برابر `null` است و فقط `priced_value` بخش قیمت‌گذاری‌شده نمایش داده می‌شود.
- `unrealized_pnl` فقط وقتی منتشر می‌شود که market value و cost basis همهٔ موقعیت‌ها معلوم باشند.
- `realized_pnl` فقط برای transaction نوع `sell` با proceeds مثبت در base asset و consumed basis معلوم محاسبه می‌شود. این عدد ادعای سود/زیان مالیاتی نیست.

## ترتیب resolution ارزش

1. identity دارایی پایه با نرخ دقیق یک؛
2. price مستقیم در base asset؛
3. FX مستقیم برای دارایی fiat؛
4. price به یک quote دیگر به‌علاوه دقیقاً یک FX مستقیم از quote به base؛
5. manual valuation پرتفوی؛
6. وضعیت صریح `missing`.

وارون‌سازی ضمنی FX، graph چندمرحله‌ای، interpolation و forward-fill خاموش‌اند. در conversion ترکیبی، lineage هر دو evidence در پاسخ حفظ می‌شود.

## Performance محدود

مسیر performance بین ۲ تا ۳۲ نقطه و حداکثر ۳۶۶ روز می‌پذیرد. بازده هر زیربازه به شکل زیر محاسبه می‌شود:

`(ending NAV - starting NAV - external flows) / starting NAV`

`opening_balance`، `deposit` و `withdrawal` جریان خارجی‌اند و با evidence موجود در زمان تراکنش به base asset تبدیل می‌شوند. بازده‌های زیربازه به‌صورت chain-linked ترکیب می‌شوند. نبود NAV، نبود valuation جریان خارجی یا NAV آغازین صفر، زیربازه را `unavailable` می‌کند و زنجیرهٔ cumulative پس از آن عددی ادعایی تولید نمی‌کند.

## API

- `GET /v1/portfolios/{portfolio_id}/analytics?as_of=...&cost_basis_method=fifo`
- `GET /v1/portfolios/{portfolio_id}/performance?start_at=...&end_at=...&point_count=2&cost_basis_method=fifo`

هر دو endpoint فقط owner را از session معتبر می‌گیرند، read-only هستند و owner ID را از query یا body قبول نمی‌کنند.

## موارد خارج از مرحله

Paper/Shadow projection، سفارش زنده، انتقال وجه، credential صرافی، کلید یا signing کیف پول، اتصال مستقیم به دیتابیس TRD Bot، SaaS/multi-user، اجرای خودکار AI، ML و هر نوع توصیهٔ مالی یا مالیاتی وارد P2-07 نشده‌اند. ورود به P2-08 تنها بعد از Freeze مستقل P2-07 مجاز است.
