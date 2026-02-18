import asyncio
import os
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

# حل مشكلة الـ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# دالة التأكد من وجود المتصفح (مهمة جداً لـ Render)
def install_playwright_browsers():
    try:
        print("Checking Playwright browsers...")
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("Chromium installed successfully!")
    except Exception as e:
        print(f"Error installing browsers: {e}")

# استدعاء التثبيت عند بدء التشغيل
install_playwright_browsers()

@app.get("/")
async def health_check():
    return {"status": "Server is running!", "info": "Ready for tasks"}

@app.get("/api/start-insta-task")
async def start_insta_task(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")

    async with async_playwright() as p:
        try:
            # تشغيل المتصفح بأخف إعدادات
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--single-process",
                    "--disable-gpu"
                ]
            )
            
            context = await browser.new_context()
            page = await context.new_page()
            
            # منع تحميل الصور لتسريع العملية
            await page.route("**/*.{png,jpg,jpeg,svg,woff,ttf}", lambda route: route.abort())

            # مثال: التوجه لموقع الاختبار أو موقعك
            # await page.goto("https://example.com") 
            
            # بيانات وهمية للتجربة الآن
            result = {
                "status": "READY",
                "user": f"insta_user_{user_id[:4]}",
                "pass": "Pass@778899",
                "msg": "تم إنشاء الحساب بنجاح"
            }

            await browser.close()
            return result

        except Exception as e:
            # في حال حدث خطأ، نغلق المتصفح ونرسل الخطأ
            print(f"Task Error: {e}")
            return {"status": "ERROR", "message": str(e)}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    return {"code": "885522"}

@app.post("/api/submit-2fa")
async def submit_2fa(data: dict):
    return {"status": "SUCCESS"}
