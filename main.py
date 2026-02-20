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
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--single-process"])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        # دخول الموقع
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # التوجه للمهمة
        target_url = TASK_URLS.get(task_type.lower(), TASK_URLS["gmail"])
        await page.goto(target_url, timeout=60000)
        
        # انتظار طويل شوي للتأكد إن كل شي ظهر (10 ثواني)
        await asyncio.sleep(10)

        # --- بداية السحب العميق ---
        # 1. سحب كل النصوص
        text_content = await page.evaluate("() => document.body.innerText")
        
        # 2. سحب كل القيم من مربعات الإدخال (Inputs) - هاد هو السر!
        input_values = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input, textarea')).map(el => el.value);
        }""")
        all_data_string = text_content + " " + " ".join(input_values)
        
        res = {"email": "N/A", "password": "N/A", "first_name": "N/A", "recovery_email": "N/A"}

        # سحب الإيميلات (Regex)
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', all_data_string)
        for m in emails:
            if "@gmail.com" in m.lower() and res["email"] == "N/A": res["email"] = m
            elif m.lower() != res["email"].lower(): res["recovery_email"] = m

        # سحب الباسورد والاسم من الـ Inputs مباشرة
        # غالباً الموقع بيحط الباسورد في حقل جنبه كلمة "copy"
        for val in input_values:
            val = val.strip()
            if not val or len(val) < 4: continue
            
            # إذا كان النص فيه أرقام وحروف كبيرة وصغيرة (احتمال كبير باسورد)
            if any(c.isdigit() for c in val) and any(c.isupper() for c in val) and "@" not in val:
                if res["password"] == "N/A": res["password"] = val
            
            # إذا كان نص بسيط (احتمال اسم)
            if val.isalpha() and len(val) < 15 and res["first_name"] == "N/A" and val.lower() not in ["copy", "submit"]:
                res["first_name"] = val

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        return {"status": "READY", "data": res}

    except Exception as e:
        if browser: await browser.close()
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/finish-task")
async def finish_task(user_id: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # 1. الضغط على Submit Report
        submit_btn = page.locator('button:has-text("Submit Report")')
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await asyncio.sleep(4)
            
        # 2. فحص رسالة الخطأ (Email does not exist / Please register account properly)
        # استخدمنا فحص النص لضمان مسك أي رسالة فشل
        error_detected = await page.evaluate("""() => {
            const bodyText = document.body.innerText;
            return bodyText.includes("does not exist") || bodyText.includes("properly") || bodyText.includes("failed");
        }""")

        if error_detected:
            # إذا فشل، نضغط على زر Back to Task باستخدام الكلاس اللي بعته
            back_btn = page.locator('button.primary:has-text("Back to Task")')
            if await back_btn.count() > 0:
                await back_btn.click()
                await asyncio.sleep(2)
            
            # ملاحظة: هنا ما بنسكر المتصفح (عشان يقدر يرجع يحاول)
            return {"status": "RETRY_NEEDED", "message": "Site rejected data. Browser is still on task page."}

        # 3. إذا لم يوجد خطأ، ننهي كل شيء
        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "SUCCESS"}
        
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

