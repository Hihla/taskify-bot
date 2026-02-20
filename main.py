import asyncio
import os
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
    return {"status": "online", "message": "Sniper is live"}

@app.get("/api/start-task")
async def start_task(user_id: str, task_type: str = "gmail"):
    p = None
    browser = None
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--single-process"])
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
        
        # انتظار "مقدس" لظهور الجداول (12 ثانية)
        await asyncio.sleep(12)

        # --- السحب الذكي وفك الكتلة ---
        raw_text = await page.evaluate("() => document.body.innerText")
        
        res = {
            "email": "N/A",
            "password": "N/A",
            "first_name": "N/A",
            "recovery_email": "N/A"
        }

        # 1. صيد الإيميل الأساسي (أول جيميل)
        email_match = re.search(r'[a-zA-Z0-9_.+-]+@gmail\.com', raw_text)
        if email_match: res["email"] = email_match.group(0)

        # 2. صيد الباسورد (ما بين كلمة PASSWORD وكلمة FIRST NAME)
        pass_match = re.search(r'PASSWORD\n(.*?)\nFIRST NAME', raw_text, re.DOTALL)
        if pass_match: res["password"] = pass_match.group(1).strip()

        # 3. صيد الاسم الأول (ما بين كلمة FIRST NAME وكلمة REZ MAIL)
        name_match = re.search(r'FIRST NAME\n(.*?)\nREZ MAIL', raw_text, re.DOTALL)
        if name_match: res["first_name"] = name_match.group(1).strip()

        # 4. صيد بريد الاسترداد (ما بين كلمة REZ MAIL وكلمة Task Instructions)
        recovery_match = re.search(r'REZ MAIL\n(.*?)\n', raw_text)
        if recovery_match: 
            res["recovery_email"] = recovery_match.group(1).replace("COPY", "").strip()
        else:
            # محاولة تانية لو كان الصيغة مختلفة
            all_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_text)
            for m in all_emails:
                if "@gmail.com" not in m.lower():
                    res["recovery_email"] = m
                    break

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        return {"status": "READY", "data": res}
    except Exception as e:
        if browser: await browser.close()
        return {"status": "ERROR", "message": str(e)}

# --- دالة إنهاء المهمة والرجوع الذكي ---
@app.get("/api/finish-task")
async def finish_task(user_id: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        submit_btn = page.locator('button:has-text("Submit Report")')
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await asyncio.sleep(4)
            
        error_detected = await page.evaluate("""() => {
            const t = document.body.innerText.toLowerCase();
            return t.includes("exist") || t.includes("properly") || t.includes("failed");
        }""")

        if error_detected:
            # الضغط على زر الرجوع Back to Task
            back_btn = page.locator('button.primary, button:has-text("Back to Task")')
            if await back_btn.count() > 0:
                await back_btn.click()
                await asyncio.sleep(2)
            return {"status": "RETRY_NEEDED", "message": "Site rejected. Try again."}

        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "SUCCESS"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

if __name__ == "__main__":
    # تأكد إن البورت هو 10000 لريندر
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

