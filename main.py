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
            # 1. تسجيل الدخول
            await page.goto(LOGIN_URL, timeout=60000)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            # 2. الضغط على زر المهمة (استهداف دقيق)
            # سنبحث عن زر Start Task الذي لا يتبعه كلمة Home أو Dashboard
            task_btn = page.locator('button:has-text("Start Task"), .btn-success, a:has-text("Start")').first
            await task_btn.click()
            
            # 3. الانتظار الذهبي (زيادة الوقت لضمان ظهور اليوزر والباسورد الحقيقيين)
            await asyncio.sleep(12) 

            # 4. استخراج البيانات من "حقول الإدخال" أولاً (لأنها الأضمن)
            # أغلب المواقع تضع اليوزر والباسورد داخل <input readonly>
            raw_inputs = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input'))
                            .map(el => el.value)
                            .filter(v => v && v.length > 3 && !v.includes('http'));
            }""")

            # 5. استخراج النصوص (فلترة الكلمات العامة مثل Home و WebEarn)
            all_text = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in all_text.split('\n') if len(l.strip()) > 3]
            
            # منع الكلمات المزعجة التي ظهرت لك
            forbidden = ["Home", "WebEarn", "Dashboard", "Logout", "Menu", "Navigation"]
            clean_lines = [l for l in lines if not any(f in l for f in forbidden)]

            acc_data = {"user": "N/A", "pass": "N/A", "name": "N/A", "email": "N/A"}
            
            # صيد الإيميل بالـ Regex
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', all_text)
            acc_data["email"] = emails[0] if emails else "N/A"

            # إذا وجدنا مدخلات (Inputs)، فهي الأولوية
            if len(raw_inputs) >= 2:
                acc_data["user"] = raw_inputs[0]
                acc_data["pass"] = raw_inputs[1]
                if len(raw_inputs) > 2: acc_data["name"] = raw_inputs[2]
            else:
                # محاولة أخيرة من النصوص المفلترة
                if len(clean_lines) >= 2:
                    acc_data["user"] = clean_lines[0]
                    acc_data["pass"] = clean_lines[1]

            await browser.close()
            return {"status": "READY", "data": acc_data}

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": str(e)}
