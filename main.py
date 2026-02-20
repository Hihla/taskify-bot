import asyncio
import os
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# حل مشكلة المسار في ريندر (Executable doesn't exist)
PW_PATH = os.path.join(os.getcwd(), "pw-browsers")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PW_PATH

TASK_URLS = {
    "instagram": "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start",
    "gmail": "https://webearn.top/task/9fce83bb-179d-4eeb-b4fa-add54cf5ca7a/start"
}
LOGIN_URL = "https://webearn.top/login"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

active_sessions = {}

@app.get("/")
async def root():
    return {"status": "online", "message": "Sniper is ready", "path": PW_PATH}

@app.get("/api/start-task")
async def start_task(user_id: str, task_type: str = "instagram"):
    p = None
    browser = None
    try:
        p = await async_playwright().start()
        # تشغيل المتصفح مع تجاهل أخطاء الـ GPU والشهادات
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--single-process", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        # 1. تسجيل الدخول
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # 2. التوجه للمهمة (جيميل أو غيره)
        target_url = TASK_URLS.get(task_type.lower(), TASK_URLS["instagram"])
        await page.goto(target_url, timeout=60000)
        
        # انتظار إضافي للجيميل لأن بياناته تتأخر في الظهور
        await asyncio.sleep(10) 

        # 3. استخراج البيانات بذكاء (البحث عن النصوص القريبة من العناوين)
        content = await page.content()
        text = await page.evaluate("() => document.body.innerText")
        
        res = {"user": "N/A", "pass": "N/A", "email": "N/A", "name": "N/A"}
        
        # استخراج الإيميل باستخدام Regex (أدق طريقة للجيميل)
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@gmail\.com', text)
        if emails: res["email"] = emails[0]

        # استخراج الباسورد واليوزر عبر البحث عن الكلمات الدلالية
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            line_up = line.upper()
            if "LOGIN" in line_up or "USERNAME" in line_up:
                if i+1 < len(lines): res["user"] = lines[i+1].replace("COPY", "").strip()
            if "PASSWORD" in line_up:
                if i+1 < len(lines): res["pass"] = lines[i+1].replace("COPY", "").strip()
            if "NAME" in line_up:
                if i+1 < len(lines): res["name"] = lines[i+1].replace("COPY", "").strip()

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        return {"status": "READY", "data": res}

    except Exception as e:
        if browser: await browser.close()
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # محاولة الضغط على زر التوليد إذا وجد
        await page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('OTP') || b.innerText.includes('Generate'));
            if(btn) btn.click();
        }""")
        await asyncio.sleep(5)
        
        text = await page.evaluate("() => document.body.innerText")
        code = re.search(r'\b\d{6}\b', text)
        return {"status": "SUCCESS", "code": code.group(0)} if code else {"status": "WAITING"}
    except:
        return {"status": "ERROR"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
