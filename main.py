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
# الرابط المباشر الذي أعطيتني إياه
INSTA_TASK_URL = "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

def ensure_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Browser install log: {e}")

ensure_browsers()

@app.get("/api/start-task")
async def start_task(user_id: str, task_type: str = "instagram"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        try:
            # 1. تسجيل الدخول السريع
            await page.goto(LOGIN_URL, timeout=60000)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            # 2. القفز المباشر لصفحة المهمة (بدون الضغط على أي زر)
            await page.goto(INSTA_TASK_URL, timeout=60000)
            
            # 3. انتظار تحميل الحقول (8 ثوانٍ مثل كودك القديم)
            await asyncio.sleep(8) 

            # 4. صيد البيانات من الحقول (الهدف الأساسي)
            # سنبحث عن أي input يكون readonly أو فيه بيانات
            data_fields = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input'))
                            .map(el => el.value)
                            .filter(v => v && v.length > 2 && !v.includes('http'));
            }""")

            # 5. صيد الإيميل والبيانات من النصوص إذا فشلت الحقول
            all_content = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in all_content.split('\n') if len(l.strip()) > 3]
            
            # صيد الإيميل بالـ Regex
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', all_content)

            await browser.close()

            # تحديد النتيجة النهائية
            # إذا كان الموقع يضع LOGIN و PASSWORD كنصوص عادية
            res_user = "N/A"
            res_pass = "N/A"
            
            if len(data_fields) >= 2:
                res_user = data_fields[0]
                res_pass = data_fields[1]
            elif "LOGIN" in lines:
                res_user = lines[lines.index("LOGIN") + 1]
                if "PASSWORD" in lines:
                    res_pass = lines[lines.index("PASSWORD") + 1]

            return {
                "status": "READY",
                "data": {
                    "user": res_user.replace("COPY", "").strip(),
                    "pass": res_pass.replace("COPY", "").strip(),
                    "email": emails[0] if emails else "N/A",
                    "name": "Insta Worker"
                }
            }

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": f"خطأ في الوصول للمهمة: {str(e)}"}
