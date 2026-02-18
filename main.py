import asyncio
import os
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

# حل مشكلة CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# بيانات تسجيل الدخول للموقع (من كودك القديم)
LOGIN_URL = "https://webearn.top/login"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

def ensure_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Browser install log: {e}")

ensure_browsers()

@app.get("/")
async def health():
    return {"status": "Server is Live", "target": "WebEarn Automated"}

@app.get("/api/start-insta-task")
async def start_insta_task(user_id: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1. تسجيل الدخول
            await page.goto(LOGIN_URL)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            
            # 2. البحث عن زر البدء والضغط عليه
            # سننتظر حتى يظهر أي عنصر قابل للنقر يحتوي على كلمة Start
            start_selector = 'button:has-text("Start"), a:has-text("Start"), .btn-primary'
            await page.wait_for_selector(start_selector, timeout=20000)
            await page.click(start_selector)

            # 3. الانتظار الحرج (هنا السحر)
            # سننتظر حتى يظهر رمز "@" في الصفحة (دليل على ظهور الإيميل)
            await page.wait_for_function('() => document.body.innerText.includes("@")', timeout=30000)
            await asyncio.sleep(2) # وقت إضافي للاستقرار

            # 4. استخراج كافة النصوص من الصفحة وتحويلها لمصفوفة
            all_text = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in all_text.split('\n') if len(l.strip()) > 1]
            
            # 5. تحليل الأسطر لجلب البيانات (من كودك القديم المضمون)
            # سنبحث عن الإيميل أولاً لأنه العلامة المميزة
            acc_email = next((s for s in lines if "@" in s), "غير متوفر")
            
            # غالباً البيانات تكون مرتبة خلف بعضها في هذه المواقع
            # سنحاول جلب القيم التي تلي كلمات مفتاحية معينة
            res = {
                "status": "READY",
                "user": "غير متوفر",
                "pass": "غير متوفر",
                "name": "غير متوفر",
                "email": acc_email
            }

            # محاولة ذكية: جلب أول 4 نصوص طويلة تظهر بعد الضغط على Start
            # عادة تكون: يوزر، باس، اسم، إيميل
            clean_lines = [l for l in lines if len(l) > 4 and "Start" not in l and "Logout" not in l]
            
            if len(clean_lines) >= 3:
                res["user"] = clean_lines[0]
                res["pass"] = clean_lines[1]
                res["name"] = clean_lines[2]

            await browser.close()
            return res

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": f"فشل الاستخراج: {str(e)}"}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    # مرحلة الضغط على "Search Email for Code"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            # تسجيل دخول سريع (يفضل لاحقاً استخدام Cookies)
            await page.goto(LOGIN_URL)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            
            # الضغط على زر جلب الكود
            await page.click('button:has-text("Search Email for Code")')
            
            # الانتظار حتى يظهر الكود باللون الأخضر (timeout 2 min)
            await page.wait_for_selector('.text-success', timeout=120000)
            code = (await page.locator('.text-success').inner_text()).strip()
            
            await browser.close()
            return {"code": code}
        except Exception as e:
            await browser.close()
            return {"code": "لم يصل بعد", "error": str(e)}

@app.post("/api/submit-2fa")
async def submit_2fa(data: dict):
    # مرحلة الـ Submit Report النهائية
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            await page.goto(LOGIN_URL)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            
            # وضع السيكريت كود (إذا كان الموقع يطلبه في هذه المرحلة)
            # await page.fill('#secret-input', data.get("secret_code"))
            
            # الضغط على زر إرسال التقرير
            await page.click('button:has-text("Submit Report")')
            
            await browser.close()
            return {"status": "SUCCESS"}
        except:
            await browser.close()
            return {"status": "ERROR"}


