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
    """ส่งข้อความวันละครั้ง ในช่วง 9:00-9:15 น. (ส่งครั้งแรกที่บอทตื่น)"""
    last_sent_date = None
    
    while True:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_hour = now.hour
        current_minute = now.minute
        
        # ตรวจสอบว่าอยู่ในช่วง 9:00-9:15 น. หรือไม่
        in_send_window = (current_hour == 9 and current_minute < 15)
        
        # ตรวจสอบว่าวันนี้ส่งแล้วหรือยัง
        already_sent_today = (last_sent_date == current_date)
        
        if in_send_window and not already_sent_today:
            # อยู่ในช่วงเวลาที่ส่งได้ และยังไม่ได้ส่งวันนี้
            print(f"✅ อยู่ในช่วงส่งข้อความ ({now.strftime('%H:%M')}) กำลังส่ง...")
            send_countdown_message()
            last_sent_date = current_date
            print(f"📅 ส่งข้อความสำเร็จ! วันที่ {current_date} เวลา {now.strftime('%H:%M:%S')}")
            # รอ 1 ชั่วโมงเพื่อไม่ให้ส่งซ้ำในวันเดียวกัน
            time.sleep(3600)
        elif already_sent_today:
            # ส่งไปแล้ววันนี้ รอจนถึงวันพรุ่งนี้
            tomorrow_9am = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            wait_seconds = (tomorrow_9am - now).total_seconds()
            print(f"😴 ส่งไปแล้ววันนี้ รอจนถึงพรุ่งนี้ 9:00 น. ({wait_seconds/3600:.1f} ชั่วโมง)")
            time.sleep(min(wait_seconds, 3600))  # รอสูงสุด 1 ชั่วโมงต่อรอบ
        elif current_hour < 9:
            # ยังไม่ถึง 9:00 น. รอจนถึง 9:00 น.
            today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
            wait_seconds = (today_9am - now).total_seconds()
            print(f"⏰ รอจนถึง 9:00 น. ({wait_seconds/3600:.1f} ชั่วโมง)")
            time.sleep(min(wait_seconds, 3600))  # รอสูงสุด 1 ชั่วโมงต่อรอบ
        else:
            # เลยช่วง 9:15 น. แล้ว และยังไม่ได้ส่งวันนี้ (bot อาจหลับพอดี) รอจนถึงพรุ่งนี้
            tomorrow_9am = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            wait_seconds = (tomorrow_9am - now).total_seconds()
            print(f"😢 พลาดช่วงส่งข้อความวันนี้ รอจนถึงพรุ่งนี้ 9:00 น. ({wait_seconds/3600:.1f} ชั่วโมง)")
            time.sleep(min(wait_seconds, 3600))  # รอสูงสุด 1 ชั่วโมงต่อรอบ

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