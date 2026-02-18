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
            await page.wait_for_load_state("networkidle")

            # 2. الذهاب لصفحة المهام والضغط على ابدأ
            # سنقوم بالانتظار حتى يظهر أي زر يحتوي كلمة Start
            await page.wait_for_selector('button:has-text("Start")', timeout=15000)
            await page.click('button:has-text("Start")') 

            # 3. الانتظار حتى تظهر حقول البيانات (حجر الزاوية)
            # سننتظر ظهور حقل واحد على الأقل يحتوي على قيمة
            await asyncio.sleep(7) # وقت أمان إضافي لتحميل البيانات داخل الحقول

            # 4. سحب جميع القيم من أي input موجود في الصفحة (الطريقة المضمونة)
            raw_values = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input'))
                            .map(el => el.value)
                            .filter(v => v && v.length > 2);
            }""")

            if len(raw_values) >= 2:
                # ترتيب الموقع غالباً: 0=User, 1=Pass, 2=Name, 3=Email
                # سنقوم بتعبئة البيانات بناءً على المتاح
                res = {
                    "status": "READY",
                    "user": raw_values[0] if len(raw_values) > 0 else "غير متوفر",
                    "pass": raw_values[1] if len(raw_values) > 1 else "غير متوفر",
                    "name": raw_values[2] if len(raw_values) > 2 else "غير متوفر",
                    "email": raw_values[3] if len(raw_values) > 3 else "غير متوفر"
                }
                await browser.close()
                return res
            else:
                raise Exception("البيانات لم تظهر في الحقول بعد")

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": str(e)}

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

