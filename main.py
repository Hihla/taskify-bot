from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import time
import os

app = Flask(__name__)
CORS(app)

# قاعدة بيانات مؤقتة لتخزين المتصفحات النشطة (في الإنتاج يفضل استخدام Redis)
user_sessions = {}

def get_browser_context(playwright, user_id):
    # إنشاء مجلد بيانات لكل مستخدم لضمان عدم التداخل
    user_data_dir = f"./user_data/{user_id}"
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    
    return playwright.chromium.launch_persistent_context(
        user_data_dir,
        headless=True,  # اجعلها False إذا كنت تريد التصحيح محلياً
        args=["--no-sandbox", "--disable-setuid-sandbox"]
    )

@app.route('/api/start-task', methods=['GET'])
def start_task():
    user_id = request.args.get('user_id')
    task_type = request.args.get('task_type')
    
    if not user_id or not task_type:
        return jsonify({"status": "ERROR", "message": "Missing parameters"}), 400

    try:
        with sync_playwright() as p:
            context = get_browser_context(p, user_id)
            page = context.new_page()
            
            # --- منطق مهمة الجيميل ---
            if task_type == "gmail":
                page.goto("https://accounts.google.com/", timeout=60000)
                # هنا نضع سكربت استخراج البيانات (مثال توضيحي)
                # ملاحظة: يجب أن يكون السكربت الفعلي يتماشى مع الموقع الذي تسحب منه الحسابات
                time.sleep(5) 
                
                # استخراج بريد الاسترداد (تعديل الاستهداف لضمان عدم ظهور N/A)
                recovery_val = "N/A"
                try:
                    # محاولة البحث عن بريد الاسترداد في صفحة الأمان
                    page.goto("https://myaccount.google.com/recovery/email", timeout=30000)
                    recovery_element = page.locator('input[type="email"]').first
                    if recovery_element.is_visible():
                        recovery_val = recovery_element.get_attribute("value")
                except:
                    recovery_val = "N/A"

                data = {
                    "user": "N/A",
                    "pass": "PASS_HERE", # استبدله بمتغير الباسورد الفعلي
                    "email": "EMAIL_HERE", # استبدله بمتغير الإيميل الفعلي
                    "first_name": "User",
                    "recovery": recovery_val,
                    "task_type": "gmail"
                }

            # --- منطق مهمة إنستغرام ---
            else:
                page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
                # هنا سكربت الدخول واستخراج البيانات
                data = {
                    "user": "INSTA_USER",
                    "pass": "INSTA_PASS",
                    "email": "INSTA_EMAIL",
                    "first_name": "InstaUser",
                    "task_type": "instagram"
                }

            return jsonify({"status": "READY", "data": data})

    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/api/get-otp', methods=['GET'])
def get_otp():
    user_id = request.args.get('user_id')
    try:
        # تأكد من أن السيرفر ينتظر وصول الرسالة فعلاً
        # سنقوم بفتح صفحة البريد أو لوحة التحكم لجلب الكود
        with sync_playwright() as p:
            context = get_browser_context(p, user_id)
            page = context.pages[0] if context.pages else context.new_page()
            
            # مثال: الانتقال لموقع استلام الكود (أو عمل Refresh للرسائل)
            # ننتظر 10 ثواني لضمان وصول الكود
            time.sleep(10) 
            
            # استهداف كود الـ OTP (تعديل الـ Selector حسب الموقع اللي بتجيب منه الكود)
            otp_element = page.locator('span.otp-code, div.verification-code').first
            if otp_element.is_visible():
                otp_code = otp_element.inner_text()
                return jsonify({"status": "SUCCESS", "code": otp_code})
            else:
                return jsonify({"status": "FAILED", "message": "الكود لم يصل بعد، حاول مجدداً"}), 404
    except Exception as e:
        return jsonify({"status": "ERROR", "message": "فشل الاتصال بالمتصفح"}), 500

@app.route('/api/submit-2fa', methods=['GET'])
def submit_2fa():
    user_id = request.args.get('user_id')
    secret = request.args.get('secret')
    # منطق توليد كود 2FA باستخدام مكتبة pyotp
    import pyotp
    try:
        totp = pyotp.TOTP(secret.replace(" ", ""))
        final_code = totp.now()
        return jsonify({"status": "SUCCESS", "final_code": final_code})
    except:
        return jsonify({"status": "ERROR", "message": "Invalid Secret Key"}), 400

@app.route('/api/finish-task', methods=['GET'])
def finish_task():
    # منطق التأكد من إنهاء المهمة في المتصفح قبل الإغلاق
    return jsonify({"status": "SUCCESS", "message": "Task Completed"})

if __name__ == '__main__':
    # تأكد من تثبيت المتصفحات على Render
    # os.system("playwright install chromium")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
