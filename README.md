# YasinRelay Core v2

پلی بین کانال‌های تلگرام و ایتا: محتوا را دریافت می‌کند، با AI پردازش می‌کند، و در یک کانال ایتا منتشر می‌کند.

در نسخه ۲ هسته، قابلیت‌های کلیدی جدیدی مانند **ذخیره‌سازی دیتابیس محلی (SQLite)**، **سیستم هوشمند حذف تکراری‌ها (Deduplication)**، **زمان‌بند سبک بومی (Scheduler)**، **پیکربندی منعطف** و **سیستم لاگینگ ساختاریافته** پیاده‌سازی شده‌اند.

---

## نمودار معماری هسته v2

```
                       [Telegram Channels]
                                |
                                v
                       +----------------+
                       |  Fetch Layer   |  <- Subprocess Go CLI
                       +--------+-------+
                                |
                                v (Fetched Posts)
                       +--------+-------+
                       | Storage Layer  |  <- SQLite Deduplication Check
                       +--------+-------+
                                |
                                v (Unique Posts Only)
                       +--------+-------+
                       | Processing L.  |  <- AI / Media Processors
                       +--------+-------+
                                |
                                v (Polished Posts)
                       +--------+-------+
                       | Publish Layer  |  <- Eitaa / Eitaayar Publisher
                       +----------------+
```

---

## نصب و راه‌اندازی

### ۱. پیش‌نیازها
مطمئن شوید پایتون ۳.۸+ و Go روی سیستم شما نصب هستند.

### ۲. شبیه‌سازی و نصب وابستگی‌ها
```bash
git clone https://github.com/yusi20006-max/YasinRelay.git
cd YasinRelay
pip install -r requirements.txt
```

### ۳. کامپایل باینری دریافت‌کننده (Go CLI)
```bash
cd fetcher
go build -o openfeed-fetch main.go
cd ..
```

### ۴. ساخت فایل تنظیمات محیطی (.env)
یک فایل `.env` بر اساس نمونه بسازید و مقادیر را پر کنید:
```bash
cp .env.example .env
```

---

## متغیرهای پیکربندی (Environment Variables)

پروژه به طور کامل از متغیرهای محیطی زیر پشتیبانی می‌کند:

| متغیر | مقدار پیش‌فرض | توضیحات |
| :--- | :--- | :--- |
| `EITAA_TOKEN` | - | توکن بات/حساب کاربری ایتایار |
| `EITAA_CHANNEL` | - | کانال مقصد ایتا (مانند `@my_channel`) |
| `SOURCE_CHANNELS` | - | کانال‌های منبع تلگرام (جداشده با کاما) |
| `DATABASE_PATH` | `relay.db` | مسیر فایل دیتابیس SQLite |
| `LOG_LEVEL` | `INFO` | سطح لاگینگ سیستم (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `FETCH_INTERVAL_SECONDS` | `3600` | بازه زمان‌بندی قدیمی در حالت `--loop` |
| `SCHEDULE_INTERVAL` | `1800` | بازه زمان‌بندی جدید در حالت `--schedule` (ثانیه) |
| `AI_PROVIDER` | `passthrough` | ارائه‌دهنده سرویس هوش مصنوعی |
| `AI_API_KEY` | - | کلید دسترسی API برای هوش مصنوعی |
| `AI_BASE_URL` | `https://api.openai.com/v1` | آدرس پایه API هوش مصنوعی |
| `AI_MODEL` | `gpt-4o-mini` | مدل زبان مورد استفاده |

---

## نحوه اجرا و حالت‌های کاربری

هسته YasinRelay سه حالت اصلی برای اجرا ارائه می‌دهد:

### ۱. اجرای تکی و ساده (Single Run)
کل پایپ‌لاین را برای تمام کانال‌های منبع یک بار اجرا کرده و متوقف می‌شود:
```bash
python3 -m yasinrelay.cli run
```

برای اعمال محدودیت در تعداد دریافت هر کانال:
```bash
python3 -m yasinrelay.cli run --limit 5
```

برای اجرای اختصاصی روی یک کانال خاص:
```bash
python3 -m yasinrelay.cli run --channel @some_channel
```

### ۲. اجرای زمان‌بندی شده جدید (Recommended - Scheduled Run)
اجرا با استفاده از سیستم زمان‌بند بومی و سبک نسخه ۲ (استفاده از بازه `SCHEDULE_INTERVAL`):
```bash
python3 -m yasinrelay.cli run --schedule
```

### ۳. اجرای دوره‌ای قدیمی (Legacy Loop Run)
اجرای دوره‌ای بر اساس زمان‌بندی قدیمی (`FETCH_INTERVAL_SECONDS`):
```bash
python3 -m yasinrelay.cli run --loop
```

---

## مستندات توسعه و تست‌ها

### ساختار دایرکتوری‌های پروژه
```
yasinrelay/
├── yasinrelay/
│   ├── storage/          # لایه پایگاه‌داده SQLite و مدل‌ها
│   ├── ai_processor.py   # رابط AIProcessor و پردازشگرها
│   ├── media_processor.py# رابط پردازش تصویر، ویدیو و فایل
│   ├── logging_config.py # پیکربندی لاگ‌ها روی کنسول و فایل
│   ├── scheduler.py      # زمان‌بند بومی سبک
│   ├── pipeline.py       # منطق اصلی پایپ‌لاین به همراه دیتابیس و حذف تکراری‌ها
│   └── cli.py            # رابط خط فرمان (CLI)
├── fetcher/              # لایه دریافت Go (فرانت-اند تلگرام به صورت subprocess)
├── tests/                # تست‌های تستی و یکپارچه‌سازی کامل
└── logs/                 # محل ذخیره‌سازی فایل‌های لاگ (relay.log, error.log)
```

### اجرای تست‌ها
تست‌های خودکار پایتون را با دستور زیر اجرا کنید:
```bash
python3 -m pytest -v
```

تست‌های Go بخش فچر تلگرام:
```bash
cd fetcher
go test -v
cd ..
```
