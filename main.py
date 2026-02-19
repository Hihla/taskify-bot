import asyncio
import re
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

# تفعيل الـ CORS بشكل كامل لضمان عدم الحظر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# بيانات تسجيل الدخول للموقع الهدف
LOGIN_URL = "https://webearn.top/login"
INSTA_TASK_URL = "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

active_sessions = {}

@app.get("/")
async def root():
    return {"message": "Server is Running"}

@app.get("/api/start-task")
async def start_task(user_id: str):
    p = None
    browser = None
    try:
        if not user_id:
            return {"status": "ERROR", "message": "Missing user_id"}

        p = await async_playwright().start()
        # إضافة --no-sandbox ضرورية جداً لعمل Playwright على Render
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # عملية تسجيل الدخول
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # الانتقال لرابط المهمة
        await page.goto(INSTA_TASK_URL, timeout=60000)
        await asyncio.sleep(5) # انتظار بسيط لاستقرار البيانات

        content = await page.content()
        text_content = await page.evaluate("() => document.body.innerText")
        
        # استخراج البيانات بنظام البحث عن الكلمات المفتاحية
        res_data = {"user": "N/A", "pass": "N/A", "email": "N/A", "first_name": "N/A"}
        
        lines = [l.strip() for l in text_content.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            upper_line = line.upper()
            if "LOGIN" in upper_line and i+1 < len(lines): res_data["user"] = lines[i+1].replace("COPY", "").strip()
            if "PASSWORD" in upper_line and i+1 < len(lines): res_data["pass"] = lines[i+1].replace("COPY", "").strip()
            if "FIRST NAME" in upper_line and i+1 < len(lines): res_data["first_name"] = lines[i+1].replace("COPY", "").strip()

        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_content)
        res_data["email"] = emails[0] if emails else "N/A"

        # حفظ الجلسة للاستخدام في الـ OTP
        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        
        return {"status": "READY", "data": res_data}

    except Exception as e:
        if browser: await browser.close()
        if p: await p.stop()
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions:
        return {"status": "ERROR", "message": "No active session"}
    
    page = active_sessions[user_id]["page"]
    try:
        await page.click("#getCodeBtn", timeout=5000)
        
        for _ in range(10): 
            await asyncio.sleep(5)
            otp_code = await page.evaluate("""() => {
                const match = document.body.innerText.match(/\\b\\d{6}\\b/);
                return match ? match[0] : null;
            }""")
            if otp_code:
                return {"status": "SUCCESS", "code": otp_code}
        
        return {"status": "RETRY", "message": "الرمز لم يظهر بعد، حاول مجدداً"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
