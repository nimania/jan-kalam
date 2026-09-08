#!/bin/bash
# جان‌کلام — راه‌اندازِ ساده برای مک.
# روی این فایل دابل‌کلیک کن؛ خودش همه‌چیز را آماده و اپ را در مرورگر باز می‌کند.
# (بار اول کمی طول می‌کشد چون کتابخانه‌ها نصب می‌شوند.)

set -e
cd "$(dirname "$0")/backend"

echo "==============================================="
echo "   جان‌کلام — در حال آماده‌سازی..."
echo "==============================================="

# پایتون
if ! command -v python3 >/dev/null 2>&1; then
  echo "خطا: python3 روی این مک نصب نیست. از python.org نصبش کن و دوباره امتحان کن."
  read -r -p "برای بستن Enter بزن..." _
  exit 1
fi

# محیط مجازی + نصب کتابخانه‌ها (فقط بار اول)
if [ ! -d .venv ]; then
  echo "→ ساخت محیط و نصب کتابخانه‌ها (فقط همین یک بار)..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
else
  source .venv/bin/activate
fi

# دادهٔ نمونه (اگر از قبل باشد، رد می‌شود)
echo "→ آماده‌سازی دادهٔ نمونه..."
python -m scripts.seed

# باز کردن مرورگر روی اپ، کمی بعد از بالا آمدن سرور
( sleep 3; open "http://127.0.0.1:8000/" ) &

echo ""
echo "✅ آماده شد! اپ در مرورگر باز می‌شود: http://127.0.0.1:8000/"
echo "   برای بستنِ اپ، این پنجره را ببند یا Control+C بزن."
echo ""

# اجرای سرور (هم API هم اپ)
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
