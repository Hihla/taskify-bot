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

@app.get("/api/start-task") # غيرنا الاسم ليصبح عاماً لكل المهام
async def start_task(user_id: str, task_type: str = "instagram"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1. تسجيل الدخول
            await page.goto(LOGIN_URL, timeout=60000)
            await page.fill('input[name="username"]', WEB_USER)
            await page.fill('input[name="password"]', WEB_PASS)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            # 2. اختيار الزر الصحيح بناءً على نوع المهمة
            # هنا السحر: سنبحث عن الزر الذي يسبقه كلمة Instagram أو Gmail
            if task_type == "instagram":
                # يبحث عن زر Start Task الذي يأتي في سياق Instagram
                target_button = page.locator('div:has-text("Instagram") >> button:has-text("Start Task")').first
            elif task_type == "gmail":
                target_button = page.locator('div:has-text("Gmail") >> button:has-text("Start Task")').first
            else:
                target_button = page.locator('button:has-text("Start Task")').first

            await target_button.click()

            # 3. صيد البيانات (Deep Extraction)
            await asyncio.sleep(8) 
            all_texts = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in all_texts.split('\n') if len(l.strip()) > 2]
            
            acc_data = {"user": "N/A", "pass": "N/A", "name": "N/A", "email": "N/A"}
            acc_data["email"] = next((s for s in lines if "@" in s), "N/A")
            
            try:
                if "LOGIN" in lines: acc_data["user"] = lines[lines.index("LOGIN") + 1]
                if "PASSWORD" in lines: acc_data["pass"] = lines[lines.index("PASSWORD") + 1]
                if "FIRST NAME" in lines: acc_data["name"] = lines[lines.index("FIRST NAME") + 1]
            except: pass

            # تنظيف الكلمات
            for k in acc_data:
                acc_data[k] = acc_data[k].replace("COPY", "").replace("copy", "").strip()

            await browser.close()
            return {"status": "READY", "data": acc_data}

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": str(e)}
