import asyncio
import os
import re
import subprocess
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

# إعدادات CORS للسماح للتطبيق بالاتصال
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# بيانات الموقع الهدف
LOGIN_URL = "https://webearn.top/login"
INSTA_TASK_URL = "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

active_sessions = {}

# تنصيب المتصفح تلقائياً
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Browser installation info: {e}")

install_browser()

@app.get("/")
async def root():
    return {"status": "online", "message": "Taskify Server is Live 🌙"}

@app.get("/api/start-task")
async def start_task(user_id: str):
    p = None
    browser = None
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")
        page = await context.new_page()

        # 1. تسجيل الدخول
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # 2. الانتقال للمهمة
        await page.goto(INSTA_TASK_URL, timeout=60000)
        await asyncio.sleep(5) 

        # 3. استخراج البيانات كاملة
        text_content = await page.evaluate("() => document.body.innerText")
        res_data = {"user": "N/A", "pass": "N/A", "email": "N/A", "first_name": "N/A"}
        
        lines = [l.strip() for l in text_content.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            u = line.upper()
            if "LOGIN" in u and i+1 < len(lines): res_data["user"] = lines[i+1].replace("COPY", "").strip()
            if "PASSWORD" in u and i+1 < len(lines): res_data["pass"] = lines[i+1].replace("COPY", "").strip()
            if "FIRST NAME" in u and i+1 < len(lines): res_data["first_name"] = lines[i+1].replace("COPY", "").strip()

        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_content)
        res_data["email"] = emails[0] if emails else "N/A"

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        return {"status": "READY", "data": res_data}

    except Exception as e:
        if browser: await browser.close()
        if p: await p.stop()
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    page = active_sessions[user_id]["page"]
    try:
        await page.click("#getCodeBtn", timeout=5000)
        for _ in range(12): 
            await asyncio.sleep(5)
            otp_code = await page.evaluate("""() => {
                const match = document.body.innerText.match(/\\b\\d{6}\\b/);
                return match ? match[0] : null;
            }""")
            if otp_code: return {"status": "SUCCESS", "code": otp_code}
        return {"status": "RETRY"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/submit-2fa")
async def submit_2fa(user_id: str, secret: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    page = active_sessions[user_id]["page"]
    try:
        # إدخال السيكريت كود
        await page.fill('input[placeholder*="2FA"]', secret) 
        
        # حل مشكلة الزر المعطل (disabled) بناءً على الصورة
        await page.evaluate('document.getElementById("otpGenBtn").removeAttribute("disabled")')
        
        # الضغط على زر التوليد باستخدام الـ ID الصحيح
        await page.click("#otpGenBtn", timeout=10000)
        await asyncio.sleep(5)
        
        # جلب الكود النهائي المكون من 6 أرقام
        final_code = await page.evaluate("""() => {
            const match = document.body.innerText.match(/\\b\\d{6}\\b/);
            return match ? match[0] : "لم يظهر كود";
        }""")
        return {"status": "SUCCESS", "final_code": final_code}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/finish-task")
async def finish_task(user_id: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    page = active_sessions[user_id]["page"]
    try:
        # الضغط على زر Submit Report بناءً على الكلاس المرسل
        await page.click('button:has-text("Submit Report")', timeout=10000)
        
        await asyncio.sleep(2)
        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "SUCCESS"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
