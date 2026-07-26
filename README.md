# YasinRelay

پلی بین کانال‌های تلگرام و ایتا: محتوا را دریافت می‌کند، با AI پردازش
می‌کند، و در یک کانال ایتا منتشر می‌کند.

جایگزین پروژه‌های قبلی OpenFeed (نمایش PWA) و FeedBridge/YasinPress
(پردازش و انتشار) — همه در یک پروژه‌ی خودکفا.

## نصب

```bash
pip install -r requirements.txt
cp .env.example .env   # و مقادیر را پر کنید
```

## اجرای تست‌ها

```bash
python3 -m pytest tests/ -v
```

## اجرا

```bash
python3 -m yasinrelay.cli run
# یا برای یک کانال خاص:
python3 -m yasinrelay.cli run --channel @some_channel --limit 5
```

## ساختار

```
yasinrelay/
├── yasinrelay/
│   ├── __init__.py
│   ├── config.py           # تنظیمات از .env
│   ├── fetch_engine.py      # FetchEngine (Fake / Subprocess به fetcher/)
│   ├── ai_processor.py       # ContentProcessor (Passthrough / Callable)
│   ├── eitaa_publisher.py    # انتشار در ایتا از طریق API ایتایار
│   ├── pipeline.py           # fetch -> process -> publish
│   └── cli.py                 # python -m yasinrelay.cli run
├── fetcher/
│   └── README.md              # راهنمای vendor کردن کد Go از OpenFeed
├── tests/
│   └── test_yasinrelay.py
├── conftest.py
├── requirements.txt
├── .env.example
└── README.md
```

## معماری

هر جزء (FetchEngine، ContentProcessor، EitaaPublisher) یک رابط ساده
با ورودی/خروجی مشخص است و مستقل از بقیه ساخته شده، طبق همون اصل بقیه‌ی
پروژه‌های Yasin: بدون وابستگی مستقیم بین اجزا، تا بشه هرکدوم رو جدا
تست/جایگزین کرد (مثلاً fetch واقعی به‌جای FakeFetcher، یا یک
ContentProcessor واقعی که با Anthropic API ترجمه/خلاصه می‌کنه).

## کارهای باقی‌مانده (برای Jules / توسعه‌ی بعدی)

- [ ] وندور کردن کد Go از OpenFeed داخل `fetcher/` و ساخت باینری
      `openfeed-fetch` طبق `fetcher/README.md`
- [ ] پیاده‌سازی یک `ContentProcessor` واقعی (ترجمه/خلاصه با AI)
      به‌جای `PassthroughProcessor`
- [ ] زمان‌بندی اجرای دوره‌ای (`fetch_interval_seconds`) — مثلاً از
      طریق cron/Termux:Boot، مشابه بقیه‌ی بات‌های ایتای موجود
