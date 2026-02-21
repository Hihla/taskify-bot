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
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # 1. محاولة الضغط على الزر بكل الصيغ الممكنة
        otp_btn = page.locator('button:has-text("Get Code"), button:has-text("Get OTP"), .btn-info, button:has-text("طلب")')
        if await otp_btn.count() > 0:
            await otp_btn.scroll_into_view_if_needed()
            await otp_btn.click()
            # انتظار وصول الكود (ممكن يحتاج وقت)
            await asyncio.sleep(7) 

        # 2. البحث عن الكود في كل مكان (نص، حقول إدخال، سمات)
        # رح ندور على أي حقل إدخال فيه 6 أرقام
        otp_from_input = await page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input'));
            for (let i of inputs) {
                if (i.value && /^\d{6}$/.test(i.value.trim())) return i.value.trim();
            }
            return null;
        }""")

        if otp_from_input:
            return {"status": "SUCCESS", "code": otp_from_input}

        # 3. إذا ما لقيناه بحقل، ندور بالنص العادي (Regex مطور)
        content = await page.evaluate("() => document.body.innerText")
        # منشيل أي مسافات أو COPY لضمان دقة الـ Regex
        clean_content = content.replace("COPY", "").strip()
        codes = re.findall(r'\b\d{6}\b', clean_content)
        
        if codes:
            return {"status": "SUCCESS", "code": codes[-1]}

        return {"status": "ERROR", "message": "لم يظهر الكود، تأكد من الضغط مرة أخرى أو انتظر قليلاً"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
@app.get("/api/submit-2fa")
async def submit_2fa(user_id: str, secret: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # 1. الضغط على زر إضافة المصادقة الثنائية
        auth_btn = page.locator('button:has-text("2FA"), button:has-text("Authentication")')
        if await auth_btn.count() > 0:
            await auth_btn.click()
            await asyncio.sleep(2)

        # 2. تعبئة السيكريت كود
        input_field = page.locator('input[type="text"], .form-control').first
        await input_field.fill(secret)
        
        # 3. زر توليد الكود
        gen_btn = page.locator('button:has-text("Generate"), button:has-text("Submit")')
        await gen_btn.click()
        await asyncio.sleep(4)

        # 4. سحب الكود المولد النهائي
        final_content = await page.evaluate("() => document.body.innerText")
        final_codes = re.findall(r'\b\d{6}\b', final_content)
        if final_codes:
            return {"status": "SUCCESS", "final_code": final_codes[-1]}
        return {"status": "ERROR", "message": "فشل توليد كود المصادقة"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

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

