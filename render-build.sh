#!/usr/bin/env bash
set -o errexit

# تثبيت المكتبات
pip install -r requirements.txt

# تحميل ملفات المتصفح المطلوبة (هذا هو السطر الناقص!)
playwright install chromium
