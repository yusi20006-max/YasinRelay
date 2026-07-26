# fetcher/

اینجا محل قرارگیری کد Go وندورشده از [[openfeed]] است (پکیج‌های
`internal/provider` و `internal/telemirror`)، که فچ محتوای تلگرام را
از طریق زنجیره‌ی failover زیر انجام می‌دهد:

```
TeleMirror -> Google -> GoogleTranslate -> Direct
```

## کاری که باید انجام شود

1. کد مربوطه از ریپازیتوری OpenFeed را اینجا کپی/وندور کنید.
2. یک CLI کوچک روی آن بسازید که این رابط را پیاده کند:

   ```
   openfeed-fetch fetch --channel <channel> --limit <n>
   ```

   و روی stdout خروجی JSON زیر را چاپ کند:

   ```json
   [
     {"message_id": "123", "text": "...", "media_url": "https://..."},
     ...
   ]
   ```

3. باینری کامپایل‌شده را با نام `openfeed-fetch` همین‌جا (یا در مسیری
   که به `SubprocessFetcher(binary_path=...)` می‌دهید) قرار دهید.

تا زمانی که این بخش تکمیل نشده، `yasinrelay.fetch_engine.FakeFetcher`
برای تست/توسعه‌ی بقیه‌ی pipeline کافی است.
