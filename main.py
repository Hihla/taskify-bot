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
        # تعديل سطر التشغيل في start_task
        browser = await p.chromium.launch(
            headless=True, 
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage", # مهم جداً لريندر
                "--disable-gpu",
                "--no-zygote",
                "--single-process" # بيوفر رامات كتير
            ]
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
        await asyncio.sleep(12)

        raw_text = await page.evaluate("() => document.body.innerText")
        
        res = {
            "email": "N/A",
            "password": "N/A",
            "first_name": "N/A",
            "recovery_email": "N/A",
            "user": "N/A"
        }

        # منطق سحب مخصص للانستا
        if task_type.lower() == "instagram":
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for i, line in enumerate(lines):
                l_up = line.upper()
                if "LOGIN" in l_up and i + 1 < len(lines):
                    res["user"] = lines[i+1].replace("COPY", "").strip()
                if "PASSWORD" in l_up and i + 1 < len(lines):
                    res["password"] = lines[i+1].replace("COPY", "").strip()
                if "EMAIL" in l_up and i + 1 < len(lines):
                    res["email"] = lines[i+1].replace("COPY", "").strip()
                if "FIRST NAME" in l_up and i + 1 < len(lines):
                    res["first_name"] = lines[i+1].replace("COPY", "").strip()
        
        # منطق سحب مخصص للجيميل
        else:
            email_match = re.search(r'EMAIL\n(.*?)\n', raw_text, re.IGNORECASE)
            if email_match: res["email"] = email_match.group(1).replace("COPY", "").strip()
            
            pass_match = re.search(r'PASSWORD\n(.*?)\n', raw_text, re.IGNORECASE)
            if pass_match: res["password"] = pass_match.group(1).replace("COPY", "").strip()
            
            name_match = re.search(r'FIRST NAME\n(.*?)\n', raw_text, re.IGNORECASE)
            if name_match: res["first_name"] = name_match.group(1).replace("COPY", "").strip()
            
            recovery_match = re.search(r'REZ MAIL\n(.*?)\n', raw_text, re.IGNORECASE)
            if recovery_match: res["recovery_email"] = recovery_match.group(1).replace("COPY", "").strip()

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        return {"status": "READY", "data": res}
    except Exception as e:
        if browser: await browser.close()
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
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # 1. إدخال السيكريت في الحقل (باستخدام الـ Placeholder الظاهر في الصورة)
        secret_input = page.locator('input[placeholder="Paste 2FA secret key..."]')
        
        if await secret_input.count() > 0:
            await secret_input.click() # للتركيز
            await secret_input.fill("") # تنظيف
            await secret_input.fill(secret)
            await asyncio.sleep(1)
        else:
            return {"status": "ERROR", "message": "لم يتم العثور على حقل السيكريت"}

        # 2. الضغط على الزر الأصفر الظاهر في الصورة
        # نستخدم النص الكامل للزر لضمان الدقة
        generate_btn = page.locator('button:has-text("Generate OTP Code")')
        
        if await generate_btn.count() > 0:
            await generate_btn.click()
            # انتظار ظهور الكود (الموقع يحتاج وقت للمعالجة)
            await asyncio.sleep(6)
        else:
            return {"status": "ERROR", "message": "لم يتم العثور على زر التوليد"}

        # 3. سحب الكود النهائي (الموقع سيقوم بتحديث النص في الصفحة ليظهر الرمز)
        # سنبحث عن رقم مكون من 6 خانات يظهر بعد الضغط
        content = await page.evaluate("() => document.body.innerText")
        final_codes = re.findall(r'\b\d{6}\b', content)
        
        if final_codes:
            # نأخذ آخر كود ظهر (غالباً هو الكود المولد الجديد)
            return {"status": "SUCCESS", "final_code": final_codes[-1]}
        
        return {"status": "ERROR", "message": "تم إرسال السيكريت ولكن لم يظهر كود الـ 6 أرقام"}

    except Exception as e:
        return {"status": "ERROR", "message": str(e)}}

@app.get("/api/finish-task")
async def finish_task(user_id: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        await asyncio.sleep(3)
        submit_btn = page.locator('button:has-text("Submit Report"), button:has-text("Finish")')
        
        if await submit_btn.count() > 0:
            await submit_btn.scroll_into_view_if_needed()
            await asyncio.sleep(1)
            await submit_btn.click()
            await asyncio.sleep(8)
            
        error_detected = await page.evaluate("""() => {
            const t = document.body.innerText.toLowerCase();
            return t.includes("exist") || 
                   t.includes("properly") || 
                   t.includes("failed") || 
                   t.includes("not completed") ||
                   t.includes("error");
        }""")

        if error_detected:
            back_btn = page.locator('button:has-text("Back to Task"), .btn-secondary')
            if await back_btn.count() > 0:
                await back_btn.click()
            return {"status": "RETRY_NEEDED", "message": "Site rejected. Try again."}

        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "SUCCESS"}
        
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)






