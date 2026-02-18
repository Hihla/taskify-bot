import asyncio
from fastapi import FastAPI, HTTPException, Body
from playwright.async_api import async_playwright
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# السماح لتطبيق React بالاتصال بالسيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# قاموس لتخزين الجلسات (المتصفحات المفتوحة)
sessions = {}

@app.get("/")
async def health_check():
    return {"status": "Server is running!"}

@app.get("/api/start-insta-task")
async def start_task(user_id: str):
    p = await async_playwright().start()
    # تشغيل المتصفح بوضعية الخفاء (ضروري للسيرفرات)
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = await browser.new_context()
    page = await context.new_page()

    try:
        # 1. تسجيل الدخول في WebEarn
        await page.goto("https://webearn.top/login")
        await page.fill('input[name="username"]', "ddraw")
        await page.fill('input[name="password"]', "m570991m")
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")

        # 2. هنا نضع كود "الصيد" الخاص بك لجلب بيانات الحساب
        # سننتظر ظهور حقول البيانات بعد الضغط على ابدأ المهمة في الموقع
        # (تأكد من كتابة الـ selectors الصحيحة بناءً على تجربة السكربت السابقة)
        
        # مثال للبيانات المستخرجة:
        acc_data = {
            "email": "auto_generated@web.com",
            "user": "insta_tester_1",
            "pass": "Password123!",
            "name": "User Name"
        }

        # حفظ الجلسة للعودة لها لاحقاً
        sessions[user_id] = {"page": page, "browser": browser, "playwright": p}
        return acc_data

    except Exception as e:
        await browser.close()
        await p.stop()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    page = sessions[user_id]["page"]
    try:
        # الضغط على زر جلب الكود في الموقع الأصلي
        await page.click('button:has-text("Search Email for Code")')
        await asyncio.sleep(8) # وقت كافٍ لوصول الكود
        
        # استخراج الكود (عدل الـ selector إذا تغير)
        code = await page.locator('.text-success').inner_text()
        return {"code": code.strip()}
    except:
        return {"code": "جاري الانتظار..."}

@app.post("/api/submit-2fa")
async def submit_2fa(data: dict = Body(...)):
    user_id = data.get("user_id")
    secret_code = data.get("secret_code")
    
    if user_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[user_id]
    page = session["page"]
    
    try:
        # 1. وضع السيكريت كود وتوليد الـ 2FA في الموقع
        # (استخدم الـ Selectors التي تعمل في سكربتك الأصلي)
        await page.fill('input[placeholder*="2FA"]', secret_code) 
        await page.click('button:has-text("Submit"), button:has-text("Report")')
        
        # 2. إغلاق المتصفح فوراً لتوفير الرام
        await session["browser"].close()
        await session["playwright"].stop()
        del sessions[user_id]
        
        return {"status": "SUCCESS"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}