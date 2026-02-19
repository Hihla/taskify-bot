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

# بيانات تسجيل الدخول
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
    return {"status": "Server is running"}

@app.get("/api/start-insta-task")
async def start_insta_task(user_id: str):
    async with async_playwright() as p:
        # تشغيل المتصفح مع ميزة تجنب الكشف
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()

        try:
            # 1. تسجيل الدخول
            await page.goto(LOGIN_URL, timeout=60000)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")

            # 2. البحث عن المهمة والضغط على ابدأ
            # سنبحث عن أول زر "Start" متاح في الصفحة
            await page.wait_for_selector('button:has-text("Start"), a:has-text("Start")', timeout=20000)
            
            # محاولة التعامل مع فتح صفحة جديدة (إذا كان الموقع يفتح تبويب جديد)
            async with context.expect_page() as new_page_info:
                await page.get_by_role("button", name="Start").first.click()
            
            task_page = await new_page_info.value
            await task_page.wait_for_load_state("networkidle")

            # 3. محاولة سحب البيانات من التبويب الجديد
            await asyncio.sleep(10) # وقت كافٍ لتوليد الحساب
            
            # سحب كل النصوص
            content = await task_page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in content.split('\n') if len(l.strip()) > 3]
            
            # تصفية النصوص لجلب الإيميل واليوزر والباس
            # سنعتمد على الترتيب أو وجود علامات
            email = next((s for s in lines if "@" in s), "جاري التحميل...")
            
            # استراتيجية ذكية: استخراج أي نصوص بجانب "Copy" أو في حقول readonly
            raw_values = await task_page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input, span, p'))
                            .map(el => el.value || el.innerText)
                            .filter(v => v && v.length > 4 && v.length < 50);
            }""")

            await browser.close()
            return {
                "status": "READY",
                "user": raw_values[0] if len(raw_values) > 0 else "N/A",
                "pass": raw_values[1] if len(raw_values) > 1 else "N/A",
                "name": raw_values[2] if len(raw_values) > 2 else "N/A",
                "email": email
            }

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": f"فشل: {str(e)}"}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    # نفس المنطق لجلب الكود
    return {"code": "123456 (جاري الربط)"}

@app.post("/api/submit-2fa")
async def submit_2fa(data: dict):
    return {"status": "SUCCESS"}
