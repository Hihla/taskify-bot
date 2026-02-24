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
        # 1. الضغط على الزر فوراً بالقوة (بدون انتظار الـ Default timeout)
        await page.click("#getCodeBtn", timeout=5000, force=True)
        
        # 2. الفحص الذكي (فحص سريع جداً كل 0.5 ثانية)
        # رح نحاول لمدة 30 ثانية (60 محاولة * 0.5 ثانية)
        for _ in range(60): 
            # فحص سريع للمحتوى عن طريق الـ JavaScript
            otp_code = await page.evaluate("""() => {
                const text = document.body.innerText;
                // البحث عن أول كود مكون من 6 أرقام
                const match = text.match(/\\b\\d{6}\\b/);
                return match ? match[0] : null;
            }""")
            
            if otp_code: 
                return {"status": "SUCCESS", "code": otp_code}
            
            # إذا ما لقى الكود، بينتظر نص ثانية بس وبيرجع يشوف
            await asyncio.sleep(0.5)
            
        return {"status": "RETRY", "message": "انتهى الوقت ولم يظهر الكود"}
        
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
@app.get("/api/submit-2fa")
async def submit_2fa(user_id: str, secret: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # 1. الضغط على زر "التالي" - بدون انتظار ثابت
        next_step_btn = page.locator('button:has-text("Next"), button:has-text("Continue"), #otpGenBtn, button:has-text("Submit")').first
        
        if await next_step_btn.count() > 0:
            await next_step_btn.click(force=True)
            # ننتظر الحقل يظهر فوراً بدلاً من sleep(3)
            await page.locator("#tfaSecret").wait_for(state="attached", timeout=5000)

        # 2. تعبئة السيكريت
        secret_input = page.locator("#tfaSecret")
        await secret_input.fill(secret, force=True)

        # 3. الضغط على زر التوليد النهائي
        gen_btn = page.locator('button:has-text("Generate OTP Code"), #otpGenBtn').last 
        
        # التقط محتوى الصفحة الحالي قبل الضغط للمقارنة لاحقاً (اختياري للسرعة)
        await gen_btn.click(force=True)

        # --- السر هنا: الانتظار الذكي للكود ---
        # بدل sleep(7)، رح نخليه يراقب الصفحة كل نصف ثانية ويبحث عن كود جديد
        final_code = "N/A"
        for _ in range(14): # محاولات لمدة 7 ثوانٍ كحد أقصى
            await asyncio.sleep(0.5) # فحص كل نصف ثانية
            content = await page.evaluate("() => document.body.innerText")
            # نبحث عن كود مكون من 6 أرقام
            codes = re.findall(r'\b\d{6}\b', content)
            if codes:
                final_code = codes[-1]
                break # إذا وجد الكود، يخرج فوراً ولا يكمل الـ 7 ثواني

        if final_code != "N/A":
            return {"status": "SUCCESS", "final_code": final_code}
        
        return {"status": "ERROR", "message": "لم يظهر الكود، ربما الموقع بطيء"}

    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
@app.get("/api/finish-task")
async def finish_task(user_id: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        # 1. الانتظار الذكي للزر بدل الـ sleep(3)
        submit_btn = page.locator('button:has-text("Submit Report"), button:has-text("Finish")')
        await submit_btn.wait_for(state="attached", timeout=5000)
        
        # 2. الضغط السريع بالقوة
        await submit_btn.click(force=True)
        print("DEBUG: تم الضغط على إنهاء المهمة")

        # 3. مراقبة النتيجة (Polling) بدل الـ sleep(8)
        # رح نفحص كل 0.5 ثانية إذا طلعت رسالة خطأ أو نجاح
        status_result = {"status": "ERROR", "message": "Timeout waiting for confirmation"}
        
        for _ in range(16):  # محاولات لمدة 8 ثواني كحد أقصى
            await asyncio.sleep(0.5)
            
            # فحص المحتوى بالكامل
            page_text = await page.evaluate("() => document.body.innerText.toLowerCase()")
            
            # حالة الخطأ
            if any(word in page_text for word in ["exist", "properly", "failed", "not completed", "error"]):
                back_btn = page.locator('button:has-text("Back to Task"), .btn-secondary')
                if await back_btn.count() > 0:
                    await back_btn.click(force=True)
                status_result = {"status": "RETRY_NEEDED", "message": "Site rejected. Try again."}
                break
            
            # حالة النجاح (إذا اختفى الزر أو طلعت كلمة نجاح أو شكر)
            if any(word in page_text for word in ["success", "thank you", "completed", "submitted", "confirmed"]):
                status_result = {"status": "SUCCESS"}
                break
            
            # حالة إضافية: إذا الموقع رجعنا لصفحة تانية فجأة (معناها المهمة خلصت)
            if await submit_btn.count() == 0:
                status_result = {"status": "SUCCESS"}
                break

        # إذا نجحت المهمة، نسكر المتصفح وننظف الذاكرة
        if status_result["status"] == "SUCCESS":
            await active_sessions[user_id]["browser"].close()
            await active_sessions[user_id]["p"].stop()
            del active_sessions[user_id]
        
        return status_result
        
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)













