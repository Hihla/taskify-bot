import asyncio
import os
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# إعداد مسارات Playwright لتعمل في Render
# هذا السطر يخبر بايثون أين يبحث عن المتصفح الذي سنقوم بتنزيله في الـ Build
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
    return {"status": "online", "message": "WebEarn Sniper is Ready!", "pw_path": PW_PATH}

@app.get("/api/start-task")
async def start_task(user_id: str, task_type: str = "instagram"):
    try:
        p = await async_playwright().start()
        # هنا التعديل الجوهري: نترك المتصفح يبحث في المسار الذي حددناه في الأعلى
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-gpu", "--single-process"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill('input[name="username"]', WEB_USER)
        await page.fill('input[name="password"]', WEB_PASS)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        target_url = TASK_URLS.get(task_type.lower(), TASK_URLS["instagram"])
        await page.goto(target_url, timeout=60000)
        await asyncio.sleep(5)

        text_content = await page.evaluate("() => document.body.innerText")
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_content)
        
        active_sessions[user_id] = {"browser": browser, "page": page, "p": p}
        
        return {"status": "READY", "email": emails[0] if emails else "N/A"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@app.get("/api/get-otp")
async def get_otp(user_id: str):
    if user_id not in active_sessions: return {"status": "EXPIRED"}
    page = active_sessions[user_id]["page"]
    try:
        code = await page.evaluate("""() => {
            const m = document.body.innerText.match(/\\b\\d{6}\\b/);
            return m ? m[0] : null;
        }""")
        return {"status": "SUCCESS", "code": code} if code else {"status": "WAITING"}
    except:
        return {"status": "ERROR"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
