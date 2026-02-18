import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

# حل مشكلة الـ CORS نهائياً
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# دالة سريعة لفحص السيرفر
@app.get("/")
async def health_check():
    return {"status": "Server is running!"}

# الدالة الأساسية لإنشاء الحساب (مُحسنة للسرعة)
@app.get("/api/start-insta-task")
async def start_insta_task(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")

    async with async_playwright() as p:
        # تشغيل المتصفح بأخف إعدادات ممكنة لسرعة الاستجابة
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--single-process",  # لتقليل استهلاك الرام
                "--disable-gpu",      # تسريع الإقلاع في السيرفرات السحابية
                "--no-zygote"
            ]
        )
        
        # إنشاء سياق تصفح سريع (بدون تحميل صور لتوفير الوقت والبيانات)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        # منع تحميل الصور والخطوط لتسريع الصفحة 300%
        await page.route("**/*.{png,jpg,jpeg,svg,woff,ttf}", lambda route: route.abort())

        try:
            # هنا تضع منطق الدخول لموقع WebEarn وإنشاء الحساب
            # مثال سريع للبيانات التي ستظهر للمستخدم فوراً:
            await page.goto("https://www.google.com", timeout=30000) # تجربة فقط
            
            # نفترض أننا جلبنا هذه البيانات من الموقع:
            fake_user = f"user_{user_id[:5]}"
            fake_pass = "Pass@123456"

            await browser.close()
            return {
                "status": "READY",
                "user": fake_user,
                "pass": fake_pass,
                "msg": "تم تجهيز البيانات بسرعة"
            }

        except Exception as e:
            await browser.close()
            return {"status": "ERROR", "message": str(e)}

# دالة جلب الـ OTP (مُبسطة للسرعة)
@app.get("/api/get-otp")
async def get_otp(user_id: str):
    # هنا تضع منطق جلب الكود من الموقع الأصلي
    await asyncio.sleep(1) # محاكاة انتظار صغير
    return {"code": "123456"}

# دالة تقديم كود الـ 2FA
@app.post("/api/submit-2fa")
async def submit_2fa(data: dict):
    # هنا تعالج الكود الذي يرسله المستخدم
    return {"status": "SUCCESS"}
