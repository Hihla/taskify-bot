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

# إعدادات النظام السرية (الموقع الخلفي)
LOGIN_URL = "https://webearn.top/login"
INSTA_TASK_URL = "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

active_sessions = {}

def ensure_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except: pass

ensure_browsers()

@app.get("/")
async def health():
    return {"status": "System Online"}

@app.get("/api/start-task")
async def start_task(user_id: str):
    if user_id in active_sessions:
        try:
            await active_sessions[user_id]["browser"].close()
        except: pass

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    context = await browser.new_context(viewport={'width': 1280, 'height': 800})
    page = await context.new_page()

    try:
        # المرحلة 1: الاتصال بالنظام
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # المرحلة 2: توليد بيانات المهمة
        await page.goto(INSTA_TASK_URL, timeout=60000)
        await asyncio.sleep(8) 

        content = await page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in content.split('\n') if len(l.strip()) > 1]
        
        res_data = {"user": "N/A", "pass": "N/A", "email": "N/A", "first_name": "N/A"}
        
        for i, line in enumerate(lines):
            l_up = line.upper()
            if "LOGIN" in l_up and i+1 < len(lines): res_data["user"] = lines[i+1]
            if "PASSWORD" in l_up and i+1 < len(lines): res_data["pass"] = lines[i+1]
            if "FIRST NAME" in l_up and i+1 < len(lines): res_data["first_name"] = lines[i+1]

        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', content)
        res_data["email"] = emails[0] if emails else "N/A"

        # تنظيف البيانات من نصوص النسخ
        for k in res_data:
            res_data[k] = res_data[k].replace("COPY", "").replace("copy", "").strip()

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}

        return {"status": "READY", "data": res_data}

    except Exception as e:
        await browser.close()
        await p.stop()
        return {"status": "ERROR", "message": "النظام مشغول حالياً، حاول مجدداً"}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions:
        return {"status": "ERROR", "message": "يرجى بدء المعالجة أولاً"}
    
    page = active_sessions[user_id]["page"]
    try:
        # ضغط الزر باستخدام الـ ID الذي استخرجته
        await page.click("#getCodeBtn", timeout=5000)
        
        # الصبر لمدة 60 ثانية لمراقبة ظهور الكود
        try:
            await page.wait_for_selector('.text-success', timeout=60000)
            
            otp_code = await page.evaluate("""() => {
                const el = document.querySelector('.text-success');
                return el ? el.innerText.trim() : null;
            }""")
            
            if otp_code and len(otp_code) >= 4:
                return {"status": "SUCCESS", "code": otp_code}
        except:
            return {"status": "RETRY", "message": "تأخر استجابة نظام التأمين، كرر المحاولة"}

    except Exception as e:
        return {"status": "ERROR", "message": "فشل في بروتوكول جلب الرمز"}

@app.post("/api/submit-final")
async def submit_final(user_id: str, secret_code: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    page = active_sessions[user_id]["page"]
    try:
        await page.fill('input[placeholder*="2FA"], input[type="text"]', secret_code)
        await page.click('button:has-text("Submit"), button:has-text("Review")')
        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "TASK_COMPLETED"}
    except:
        return {"status": "ERROR"}
