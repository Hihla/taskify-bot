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
INSTA_TASK_URL = "https://webearn.top/task/6c9c98df-1078-4149-a376-607bd0f22df5/start"
WEB_USER = "ddraw"
WEB_PASS = "m570991m"

active_sessions = {}

@app.get("/api/start-task")
async def start_task(user_id: str):
    if user_id in active_sessions:
        try: await active_sessions[user_id]["browser"].close()
        except: pass

    p = await async_playwright().start()
    # إضافة User-Agent حقيقي عشان الموقع يفتح كأنه متصفح طبيعي
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    try:
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        await page.goto(INSTA_TASK_URL, timeout=60000)
        # ننتظر شوي زيادة عشان الموقع يولد بيانات الحساب
        await asyncio.sleep(10) 

        content = await page.evaluate("() => document.body.innerText")
        
        res_data = {"user": "N/A", "pass": "N/A", "email": "N/A", "first_name": "N/A"}
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        for i, line in enumerate(lines):
            if "LOGIN" in line.upper() and i+1 < len(lines): res_data["user"] = lines[i+1]
            if "PASSWORD" in line.upper() and i+1 < len(lines): res_data["pass"] = lines[i+1]
            if "FIRST NAME" in line.upper() and i+1 < len(lines): res_data["first_name"] = lines[i+1]

        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', content)
        res_data["email"] = emails[0] if emails else "N/A"

        # تنظيف كلمة COPY
        for k in res_data:
            res_data[k] = res_data[k].replace("COPY", "").replace("copy", "").strip()

        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        return {"status": "READY", "data": res_data}

    except Exception as e:
        return {"status": "ERROR", "message": "النظام مشغول، حاول لاحقاً"}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions:
        return {"status": "ERROR", "message": "ابدأ المهمة أولاً"}
    
    page = active_sessions[user_id]["page"]
    try:
        # ضغط الزر باستخدام الـ ID اللي جبته
        await page.click("#getCodeBtn", timeout=5000)
        
        # محاولة البحث عن الكود لمدة 60 ثانية (تكرار ذكي)
        for _ in range(12): 
            await asyncio.sleep(5)
            
            # رح نبحث عن أي نص لونه أخضر أو أي رقم 6 خانات يظهر فجأة
            otp_code = await page.evaluate("""() => {
                // البحث عن الكود في العناصر المعروفة للموقع
                const selectors = ['.text-success', '#otp_code', '.code-display'];
                for (let s of selectors) {
                    const el = document.querySelector(s);
                    if (el && /\d+/.test(el.innerText)) return el.innerText.match(/\d+/)[0];
                }
                
                // إذا لم يجد سلكتور، يبحث في كل نصوص الصفحة عن رقم 6 خانات
                const match = document.body.innerText.match(/\b\d{6}\b/);
                return match ? match[0] : null;
            }""")
            
            if otp_code:
                return {"status": "SUCCESS", "code": otp_code}
            
            # إعادة ضغط الزر إذا الموقع "نسي" يحدث
            if _ == 5: 
                try: await page.click("#getCodeBtn", timeout=2000)
                except: pass

        return {"status": "RETRY", "message": "الرمز لم يجهز بعد"}

    except Exception as e:
        return {"status": "ERROR", "message": "فشل جلب الرمز"}

@app.post("/api/submit-final")
async def submit_final(user_id: str, secret_code: str):
    if user_id not in active_sessions: return {"status": "ERROR"}
    page = active_sessions[user_id]["page"]
    try:
        await page.fill('input[placeholder*="2FA"], input[type="text"]', secret_code)
        await page.click('button:has-text("Submit"), button:has-text("Review")')
        # إنهاء الجلسة
        await active_sessions[user_id]["browser"].close()
        await active_sessions[user_id]["p"].stop()
        del active_sessions[user_id]
        return {"status": "TASK_COMPLETED"}
    except:
        return {"status": "ERROR"}
