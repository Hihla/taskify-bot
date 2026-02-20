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

# حل مشكلة المسار في ريندر
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
    return {"status": "online", "message": "Sniper is ready"}

@app.get("/api/start-task")
async def start_task(user_id: str, task_type: str = "gmail"):
    p = None
    browser = None
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--single-process"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        # تسجيل الدخول
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # التوجه للمهمة
        target_url = TASK_URLS.get(task_type.lower(), TASK_URLS["gmail"])
        await page.goto(target_url, timeout=60000)
        await asyncio.sleep(8) # انتظار تحميل البيانات بالكامل

        # 3. استخراج البيانات بذكاء شديد
        text_content = await page.evaluate("() => document.body.innerText")
        
        # استخراج كافة الإيميلات
        all_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_content)
        
        res = {
            "email": "N/A",
            "password": "N/A",
            "first_name": "N/A",
            "recovery_email": "N/A"
        }

        # فرز الإيميلات: الأول جيميل والباقي استرداد
        for mail in all_emails:
            if "@gmail.com" in mail and res["email"] == "N/A":
                res["email"] = mail
            elif mail != res["email"]:
                res["recovery_email"] = mail

        # تحليل الأسطر لجلب الباسورد والاسم
        lines = [l.strip() for l in text_content.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            l_up = line.upper()
            
            # صيد كلمة السر (نبحث عن السطر اللي بعد كلمة PASSWORD)
            if "PASSWORD" in l_up and i + 1 < len(lines):
                res["password"] = lines[i+1].replace("COPY", "").strip()
            
            # صيد الاسم (نبحث عن السطر اللي بعد FIRST NAME)
            if "FIRST NAME" in l_up and i + 1 < len(lines):
                res["first_name"] = lines[i+1].replace("COPY", "").strip()
            
            # تأكيد إضافي لبريد الاسترداد (لو فشل الـ Regex)
            if ("REZ MAIL" in l_up or "RECOVERY" in l_up) and i + 1 < len(lines):
                potential_recovery = lines[i+1].replace("COPY", "").strip()
                if "@" in potential_recovery:
                    res["recovery_email"] = potential_recovery

        # إذا لسا كلمة السر N/A، نبحث عن أي نص عشوائي مشفر قريب من حقل الباسورد
        if res["password"] == "N/A":
            for line in lines:
                if any(c.isdigit() for c in line) and any(c.isupper() for c in line) and len(line) > 6 and "@" not in line:
                    res["password"] = line.replace("COPY", "").strip()
                    break

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        return {"status": "READY", "data": res}

    except Exception as e:
        if browser: await browser.close()
        return {"status": "ERROR", "message": str(e)}

# إنهاء المهمة أو الرجوع في حال الخطأ
@app.get("/api/finish-task")
async def finish_task(user_id: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # 1. محاولة الضغط على Submit Report
        submit_btn = page.locator('button:has-text("Submit Report")')
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await asyncio.sleep(3)
            
        # 2. فحص إذا ظهرت رسالة خطأ (مثل التي في الصورة الثانية)
        error_msg = page.locator('text=This email does not exist')
        if await error_msg.count() > 0:
            # إذا ظهر خطأ، نضغط على Back to Task
            back_btn = page.locator('button:has-text("Back to Task")')
            if await back_btn.count() > 0:
                await back_btn.click()
            return {"status": "RETRY_NEEDED", "message": "Email validation failed"}

        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "SUCCESS"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
        
if __name__ == "__main__":
    # ريندر بيستخدم بورت متغير، هاد السطر بيضمن إننا نسمع للبورت الصح
    port = int(os.environ.get("PORT", 10000))
    print(f"--- Sniper Server Starting on port {port} ---")
    uvicorn.run(app, host="0.0.0.0", port=port)

