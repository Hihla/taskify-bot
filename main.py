import asyncio
import os
import subprocess
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOGIN_URL = "https://webearn.top/login"
INSTA_TASK_URL = "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

# متغيرات عالمية لحفظ الجلسة (عشان ما يسجل دخول كل مرة وتتغير البيانات)
active_sessions = {}

def ensure_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except:
        pass

ensure_browsers()

@app.get("/api/start-task")
async def start_task(user_id: str):
    # إذا كان في جلسة قديمة مفتوحة، نسكرها عشان نبدأ وحدة جديدة نظيفة
    if user_id in active_sessions:
        await active_sessions[user_id]["browser"].close()

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    context = await browser.new_context()
    page = await context.new_page()

    try:
        # 1. تسجيل الدخول
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # 2. الذهاب للمهمة
        await page.goto(INSTA_TASK_URL, timeout=60000)
        await asyncio.sleep(8)

        # 3. سحب كل البيانات بما فيها First Name
        all_content = await page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in all_content.split('\n') if len(l.strip()) > 1]
        
        res_data = {"user": "N/A", "pass": "N/A", "email": "N/A", "first_name": "Insta Worker"}
        
        # صيد البيانات بالذكاء الاصطناعي البسيط (البحث عن الكلمة وما بعدها)
        for i, line in enumerate(lines):
            line_up = line.upper()
            if "LOGIN" in line_up and i+1 < len(lines): res_data["user"] = lines[i+1]
            if "PASSWORD" in line_up and i+1 < len(lines): res_data["pass"] = lines[i+1]
            if "FIRST NAME" in line_up and i+1 < len(lines): res_data["first_name"] = lines[i+1]

        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', all_content)
        res_data["email"] = emails[0] if emails else "N/A"

        # حفظ الجلسة مفتوحة في الذاكرة
        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}

        return {"status": "READY", "data": res_data}

    except Exception as e:
        await browser.close()
        await p.stop()
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions:
        return {"status": "ERROR", "message": "يجب بدء المهمة أولاً"}
    
    page = active_sessions[user_id]["page"]
    try:
        # 1. ضغط زر جلب الكود (بدون إعادة تحميل الصفحة)
        await page.click('button:has-text("Search Email for Code")')
        
        # 2. انتظار الكود الأخضر
        await page.wait_for_selector('.text-success', timeout=120000)
        otp_code = (await page.locator('.text-success').inner_text()).strip()
        
        # 3. الضغط على الزر التالي (الانتقال للمصادقة 2FA)
        # الموقع بيفتح الزر بعد ما يظهر الكود، السكربت بينتظره ويضغطه
        next_btn = page.locator('button:has-text("Next"), button:has-text("Authentication")').first
        await next_btn.wait_for(state="visible")
        await next_btn.click()
        
        return {"status": "SUCCESS", "code": otp_code}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@app.post("/api/submit-final")
async def submit_final(user_id: str, secret_code: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    
    page = active_sessions[user_id]["page"]
    try:
        # 1. وضع السيكريت كود في مكانه
        await page.fill('input[type="text"]', secret_code) # السكربت بيعرف وين يحط الكود
        
        # 2. الضغط على زر الإنهاء أو المراجعة النهائي
        final_btn = page.locator('button:has-text("Submit"), button:has-text("Review")').first
        await final_btn.click()
        
        # إغلاق المتصفح بعد انتهاء المهمة تماماً
        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        
        return {"status": "TASK_COMPLETED"}
    except:
        return {"status": "ERROR"}
