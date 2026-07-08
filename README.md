# آمریکانو

نسخه‌ی ماژولار و سرورمحور بازی با Flask و SQLite. منطق بازی، موجودی و نتیجه‌ی خانه‌ها روی سرور نگهداری می‌شود و مرورگر به داده‌ی محرمانه یا رمز خام دسترسی ندارد.

## اجرای محلی در ویندوز

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

سپس `http://127.0.0.1:8000` را باز کنید. در حالت توسعه، اگر `.env` نسازید حساب اولیه `adminmor` با رمز موقت `13888831` ساخته می‌شود. این مقدار فقط برای اجرای محلی است.

## اجرای سرور

فایل `.env.example` را با نام `.env` کپی کنید. در آن حتماً `APP_ENV=production`، یک `SECRET_KEY` تصادفی حداقل ۳۲ نویسه‌ای و یک `ADMIN_PASSWORD` قوی قرار دهید. برای ساخت کلید می‌توانید از `python -c "import secrets; print(secrets.token_urlsafe(48))"` استفاده کنید. سپس:

```powershell
.\start_server.ps1
```

برای اینترنت، Nginx یا Caddy را جلوی Waitress قرار دهید، HTTPS را فعال کنید و از فایل `instance/poop_game.sqlite3` بکاپ منظم بگیرید. `TRUST_PROXY=1` فقط وقتی درست است که دقیقاً یک پراکسی قابل اعتماد جلوی برنامه باشد؛ در اجرای مستقیم آن را `0` کنید. مسیر سلامت سرویس `/health` است.

بکاپ سازگار در زمان روشن بودن سرویس:

```powershell
python scripts/backup_db.py --output-dir backups
```

بازیابی رمز مدیر از کنسول امن سرور:

```powershell
python scripts/reset_admin_password.py adminmor
```

## تست

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## ساختار

- `app/auth.py`: نشست، ورود و سطح دسترسی
- `app/game.py`: موتور بازی و تسویه‌ی اتمیک
- `app/admin.py`: مدیریت کاربران و گزارش ممیزی
- `app/db.py`: طرح SQLite، WAL، دفتر تراکنش و seed مدیر
- `app/static`: رابط کاربری ماژولار
- `scripts`: بکاپ آنلاین و بازیابی امن حساب مدیر
- `tests`: تست‌های ورود، امنیت، هم‌زمانی موجودی، بازی و مدیریت

اعتبار بازی در این پروژه پول واقعی یا سامانه‌ی پرداخت نیست. اگر قرار است پرداخت واقعی اضافه شود، بررسی حقوقی، احراز هویت و زیرساخت مالی جداگانه لازم است.
