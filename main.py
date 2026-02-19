from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import time
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/start-task', methods=['GET'])
def start_task():
    user_id = request.args.get('user_id')
    task_type = request.args.get('task_type')
    
    # رابط الموقع اللي فيه المهمة (حط الرابط الحقيقي هون)
    TARGET_URL = "https://example-task-site.com/login" 

    try:
        with sync_playwright() as p:
            # تشغيل المتصفح بوضع التخفي
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            # 1. الذهاب لموقع المهمة
            page.goto(TARGET_URL, timeout=60000)
            
            # 2. الانتظار حتى تحميل البيانات (تعديل الـ selectors حسب الموقع)
            # هون السكربت بيبحث عن أي نص بيشبه الإيميل أو كلمة السر
            time.sleep(5) # انتظار أولي للتحميل
            
            # --- محرك الاقتناص الذكي ---
            # بنحاول نسحب البيانات بناءً على أماكنها المتوقعة في صفحة المهمة
            extracted_email = "N/A"
            extracted_pass = "N/A"
            extracted_recovery = "N/A"
            extracted_name = "User"

            try:
                # اقتناص الإيميل (بيبحث عن @)
                email_element = page.locator('text=/.*@gmail\\.com/').first
                if email_element.is_visible():
                    extracted_email = email_element.inner_text()

                # اقتناص كلمة السر (بيبحث عن حقل باسورد أو نص بجانب كلمة "Password")
                # ملاحظة: هون لازم نعدل السلكتور حسب شو بيظهر بالموقع عندك
                pass_element = page.locator('input[type="password"]').first
                if pass_element.is_visible():
                    extracted_pass = pass_element.get_attribute("value") or pass_element.inner_text()
                
                # اقتناص بريد الاسترداد
                # بيبحث عن كلمة "Recovery" أو إيميل تاني موجود بالصفحة
                recovery_element = page.locator('text=/Recovery|استرداد/').first
                # (هنا نضع منطق جلب النص القريب من كلمة استرداد)
            except:
                pass

            # إذا فشل الاقتناص الآلي، السكربت بيبعت "جاري المحاولة" أو N/A
            data = {
                "user": "N/A",
                "email": extracted_email if extracted_email != "N/A" else "جاري السحب...",
                "pass": extracted_pass if extracted_pass != "N/A" else "جاري السحب...",
                "first_name": extracted_name,
                "recovery": extracted_recovery,
                "task_type": task_type
            }

            browser.close()
            return jsonify({"status": "READY", "data": data})

    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

# باقي الدوال (get-otp, submit-2fa) تبقى كما هي
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
