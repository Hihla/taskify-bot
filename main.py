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
# الرابط المباشر للمهمة
INSTA_TASK_URL = "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

# حفظ الجلسات في الذاكرة لمنع تغير الحساب
active_sessions = {}

def ensure_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except:
        pass

ensure_browsers()

@app.get("/")
async def health():
    return {"status": "Server Online"}

@app.get("/api/start-task")
async def start_task(user_id: str):
    # إغلاق أي جلسة قديمة لنفس المستخدم
    if user_id in active_sessions:
        try:
            await active_sessions[user_id]["browser"].close()
        except: pass

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    context = await browser.new_context(viewport={'width': 1280, 'height': 800})
    page = await context.new_page()

    try:
        # 1. تسجيل الدخول
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # 2. القفز للمهمة
        await page.goto(INSTA_TASK_URL, timeout=60000)
        await asyncio.sleep(8) # انتظار توليد الحساب

        # 3. سحب البيانات (يوزر، باس، اسم، إيميل)
        content = await page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in content.split('\n') if len(l.strip()) > 1]
        
        res_data = {"user": "N/A", "pass": "N/A", "email": "N/A", "first_name": "N/A"}
        
        # البحث في الأسطر عن القيم
        for i, line in enumerate(lines):
            l_up = line.upper()
            if "LOGIN" in l_up and i+1 < len(lines): res_data["user"] = lines[i+1]
            if "PASSWORD" in l_up and i+1 < len(lines): res_data["pass"] = lines[i+1]
            if "FIRST NAME" in l_up and i+1 < len(lines): res_data["first_name"] = lines[i+1]

        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', content)
        res_data["email"] = emails[0] if emails else "N/A"

        # تنظيف كلمة COPY
        for k in res_data:
            res_data[k] = res_data[k].replace("COPY", "").replace("copy", "").strip()

        # حفظ الجلسة
        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}

        return {"status": "READY", "data": res_data}

    except Exception as e:
        await browser.close()
        await p.stop()
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions:
        return {"status": "ERROR", "message": "بدء المهمة أولاً"}
    
    page = active_sessions[user_id]["page"]
    try:
        # استخدام الـ ID الذي استخرجته (getCodeBtn)
        await page.click("#getCodeBtn", timeout=5000)
        
        # الانتظار حتى يظهر الكود (نبحث عن الكلاس text-success أو أي نص أخضر)
        # سننتظر بحد أقصى دقيقتين كما في الموقع
        await asyncio.sleep(5) # انتظار بسيط للاستجابة
        
        otp_code = await page.evaluate("""() => {
            const el = document.querySelector('.text-success');
            if (el) return el.innerText.trim();
            // محاولة صيد رقم من 6 خانات إذا لم يجد الكلاس
            const match = document.body.innerText.match(/\\b\\d{6}\\b/);
            return match ? match[0] : null;
        }""")

        if otp_code:
            return {"status": "SUCCESS", "code": otp_code}
        else:
            return {"status": "RETRY", "message": "الكود لم يظهر بعد"}

    except Exception as e:
        # محاولة بديلة إذا فشل الـ ID
        try:
            await page.click('button:has-text("Search Email")', timeout=2000)
            return {"status": "RETRY", "message": "تم الضغط، انتظر الكود"}
        except:
            return {"status": "ERROR", "message": "فشل الضغط على الزر"}

@app.post("/api/submit-final")
async def submit_final(user_id: str, secret_code: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    
    page = active_sessions[user_id]["page"]
    try:
        # 1. البحث عن حقل السيكريت كود (غالباً يكون التايب text أو number)
        await page.fill('input[placeholder*="2FA"], input[type="text"]', secret_code)
        
        # 2. ضغط زر الإنهاء
        await page.click('button:has-text("Submit"), button:has-text("Review")')
        
        # إغلاق الجلسة
        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        
        return {"status": "TASK_COMPLETED"}
    except:
        return {"status": "ERROR"}
