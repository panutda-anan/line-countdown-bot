from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from datetime import datetime, timedelta
import os
import threading
import time

app = Flask(__name__)

# ตั้งค่าจาก Environment Variables
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# ตั้งค่า D-Day (รูปแบบ YYYY-MM-DD)
DDAY = datetime(2026, 1, 28)
GROUP_ID = os.getenv('LINE_GROUP_ID', '')  # จะตั้งค่าทีหลัง

def calculate_days_left():
    """คำนวณจำนวนวันที่เหลือ"""
    today = datetime.now()
    delta = DDAY - today
    return delta.days

def send_countdown_message():
    """ส่งข้อความ countdown ไปกลุ่ม"""
    if not GROUP_ID:
        print("ยังไม่ได้ตั้งค่า GROUP_ID")
        return
    
    days_left = calculate_days_left()
    message_text = f"🎯 นับถอยหลัง D-Day!\n\n📅 เหลืออีก {days_left} วัน\nถึงวันที่ {DDAY.strftime('%d/%m/%Y')}\n\n💪 Fighting!"
    
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=GROUP_ID,
                    messages=[TextMessage(text=message_text)]
                )
            )
        print(f"✅ ส่งข้อความสำเร็จ! เหลืออีก {days_left} วัน")
    except Exception as e:
        print(f"❌ Error: {e}")

def schedule_daily_message():
    """ส่งข้อความทุกวันเวลา 9:00 น."""
    while True:
        now = datetime.now()
        # ตั้งเวลาส่งข้อความ 9:00 น.
        target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # ถ้าเลย 9 โมงแล้ว ให้ส่งพรุ่งนี้
        if now > target_time:
            target_time += timedelta(days=1)
        
        # คำนวณเวลาที่ต้องรอ
        wait_seconds = (target_time - now).total_seconds()
        print(f"⏰ จะส่งข้อความอีกครั้งใน {wait_seconds/3600:.1f} ชั่วโมง")
        
        time.sleep(wait_seconds)
        send_countdown_message()

@app.route("/callback", methods=['POST'])
def callback():
    """Webhook สำหรับรับข้อความจาก LINE"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'

@app.route("/health", methods=['GET'])
def health():
    """Health check endpoint"""
    return 'Bot is running!', 200

@app.route("/test", methods=['GET'])
def test():
    """ทดสอบส่งข้อความทันที"""
    send_countdown_message()
    return f'Sent! Days left: {calculate_days_left()}', 200

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """ตอบกลับเมื่อมีคนส่งข้อความมา"""
    user_message = event.message.text.lower()
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if 'countdown' in user_message or 'นับ' in user_message:
            days_left = calculate_days_left()
            reply_text = f"📊 เหลืออีก {days_left} วัน จนถึง D-Day!\n({DDAY.strftime('%d/%m/%Y')})"
        elif 'help' in user_message or 'ช่วย' in user_message:
            reply_text = "คำสั่งที่ใช้ได้:\n• countdown - ดูวันที่เหลือ\n• help - ดูคำสั่ง\n\nบอทจะส่งข้อความอัตโนมัติทุกวัน 9:00 น. 🎯"
        else:
            reply_text = "สวัสดีครับ! พิมพ์ 'countdown' เพื่อดูวันที่เหลือ หรือ 'help' เพื่อดูคำสั่ง"
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    # เริ่ม thread สำหรับส่งข้อความอัตโนมัติ
    scheduler_thread = threading.Thread(target=schedule_daily_message, daemon=True)
    scheduler_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)