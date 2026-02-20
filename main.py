import asyncio
import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

# إعدادات CORS للسماح لتطبيقك بالاتصال بالسيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# الروابط المظلية المباشرة لـ WebEarn
TASK_URLS = {
    "instagram": "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start",
    "gmail": "https://webearn.top/task/9fce83bb-179d-4eeb-b4fa-add54cf5ca7a/start"
}
LOGIN_URL = "https://webearn.top/login"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

# تخزين الجلسات لمنع ضياع المهمة عند جلب الـ OTP
active_sessions = {}

@app.get("/")
async def root():
    return {"status": "online", "message": "WebEarn Sniper Live 🌙"}

@app.get("/api/start-task")
async def start_task(user_id: str, task_type: str = "instagram"):
    p = None
    browser = None
    try:
        p = await async_playwright().start()
        # تشغيل المتصفح بإعدادات ريندر الصارمة
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--single-process"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")
        page = await context.new_page()

        # 1. تسجيل الدخول التلقائي (النزول المظلي)
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # 2. الانتقال المباشر للمهمة
        target_url = TASK_URLS.get(task_type.lower(), TASK_URLS["instagram"])
        await page.goto(target_url, timeout=60000)
        await asyncio.sleep(5) # انتظار تحميل بيانات المهمة

        # 3. اقتناص البيانات من محتوى الصفحة
        text_content = await page.evaluate("() => document.body.innerText")
        res_data = {
            "user": "N/A", "pass": "N/A", "email": "N/A", 
            "first_name": "N/A", "recovery": "N/A", "task_type": task_type
        }
        
        lines = [l.strip() for l in text_content.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            u = line.upper()
            if "LOGIN" in u and i+1 < len(lines): res_data["user"] = lines[i+1].replace("COPY", "").strip()
            if "PASSWORD" in u and i+1 < len(lines): res_data["pass"] = lines[i+1].replace("COPY", "").strip()
            if "FIRST NAME" in u and i+1 < len(lines): res_data["first_name"] = lines[i+1].replace("COPY", "").strip()
            if "RECOVERY" in u and i+1 < len(lines): res_data["recovery"] = lines[i+1].replace("COPY", "").strip()

        # صيد الإيميل باستخدام Regex
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_content)
        if emails: res_data["email"] = emails[0]

        # حفظ الجلسة لإكمال الـ OTP لاحقاً بدون Refresh
        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        
        return {"status": "READY", "data": res_data}
    except Exception as e:
        if browser: await browser.close()
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/submit-2fa")
async def submit_2fa(user_id: str, secret: str):
    if user_id not in active_sessions:
        return {"status": "ERROR", "message": "No active session found"}
    
    page = active_sessions[user_id]["page"]
    try:
        # البحث عن خانة الـ 2FA وتعبئتها
        selector = 'input[placeholder*="2FA"]'
        await page.fill(selector, "")
        await page.type(selector, secret, delay=100)
        
        # تفعيل زر التوليد برمجياً
        await page.evaluate("""() => {
            const btn = document.getElementById("otpGenBtn");
            if(btn){ btn.removeAttribute("disabled"); btn.click(); }
        }""")
        
        await asyncio.sleep(8) # انتظار توليد الكود

        # استخراج كود الـ 6 أرقام من الصفحة
        final_code = await page.evaluate("""() => {
            const m = document.body.innerText.match(/\\b\\d{6}\\b/);
            return m ? m[0] : null;
        }""")
        
        return {"status": "SUCCESS", "final_code": final_code} if final_code else {"status": "ERROR", "message": "Code not found"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/finish-task")
async def finish_task(user_id: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    page = active_sessions[user_id]["page"]
    try:
        await page.click('button:has-text("Submit Report")', timeout=10000)
        await asyncio.sleep(3)
        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "SUCCESS"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
