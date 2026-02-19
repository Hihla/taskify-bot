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

@app.get("/")
async def health():
    return {"status": "Ready to hunt!"}

@app.get("/api/start-task")
async def start_task(user_id: str, task_type: str = "instagram"):
    async with async_playwright() as p:
        # تشغيل المتصفح مع إعدادات تجنب الكشف
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()

        try:
            # 1. تسجيل الدخول
            await page.goto(LOGIN_URL, timeout=60000)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            # 2. البحث عن الزر بأكثر من طريقة (بدون تعقيد)
            # جربنا نحدد Instagram وفشل، الآن سنجرب نضغط على أي زر "بدء مهمة" متاح
            selectors = [
                'button:has-text("Start Task")',
                'button:has-text("Start")',
                'a:has-text("Start Task")',
                '.btn-success', # غالباً أزرار البدء تكون خضراء
                'button[type="button"]'
            ]
            
            found = False
            for selector in selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=5000):
                        await btn.click()
                        found = True
                        break
                except:
                    continue
            
            if not found:
                # إذا فشل، جرب الضغط على أول زر يظهر في الصفحة بعد تسجيل الدخول
                await page.click("button")
            
            # 3. صيد البيانات (Deep Extraction)
            await asyncio.sleep(10) # وقت كافٍ لتحميل المهمة
            
            all_texts = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in all_texts.split('\n') if len(l.strip()) > 2]
            
            acc_data = {"user": "N/A", "pass": "N/A", "name": "N/A", "email": "N/A"}
            
            # استخراج الإيميل بالـ Regex (أضمن طريقة)
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', all_texts)
            acc_data["email"] = emails[0] if emails else "N/A"
            
            # محاكاة منطق البوت القديم في سحب الباقي
            try:
                for i, line in enumerate(lines):
                    if "LOGIN" in line.upper(): acc_data["user"] = lines[i+1]
                    if "PASSWORD" in line.upper(): acc_data["pass"] = lines[i+1]
                    if "FIRST NAME" in line.upper(): acc_data["name"] = lines[i+1]
            except: pass

            # إذا بقيت القيم N/A، نسحب أول نصوص تظهر (كما فعل كودك القديم)
            if acc_data["user"] == "N/A" and len(lines) > 5:
                acc_data["user"] = lines[0]
                acc_data["pass"] = lines[1]

            # تنظيف "COPY"
            for k in acc_data:
                acc_data[k] = acc_data[k].replace("COPY", "").replace("copy", "").strip()

            await browser.close()
            return {"status": "READY", "data": acc_data}

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": f"حدث خطأ أثناء التنفيذ: {str(e)}"}
