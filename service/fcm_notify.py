from firebase_admin import messaging, db
from datetime import datetime, date

# device registration token
# registration_token = "d8NlS0JqRQSiN5vWUZVx2I:APA91bH4-5ioxwC5wCJP2Sf116wa3YRe5vmbbeY5TNpJLh81_7TVFgaQIiM6pAlbz_XGo8TaFnihm3dRe6nghVzE6kTpmZTUo70deAmCmyLuKbcjLh8b8TE"

def send_notification(token, title, body, data=None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=token,
        data=data or {}  
    )
    response = messaging.send(message)
    print("Notification sent:", response)


def handle_activity_record(user_id):
    ref = db.reference("activity_records")
    result_ref = db.reference(f"user/{user_id}/deviceToken")
    device_token = result_ref.get()
    data = ref.get()

    if not data:
        # send_notification(token, "📲 Hôm nay bạn thế nào?", "Mở app ngay để xem hành trình hoạt động của bạn hôm nay nhé!")
        return

    today_str = date.today().strftime('%Y-%m-%d')  
    found_activity_today = False

    for key, record in data.items():
        if record.get("user_id") != user_id:
            continue

        date_str = record.get("date")  
        # Bỏ qua các bản ghi không phải ngày hôm nay
        if date_str != today_str:
            continue

        found_activity_today = True  # Có ít nhất 1 bản ghi của ngày hôm nay

        records = record.get("records", [])
        records.sort(key=lambda x: x['start_time'])

        current_activity = None
        group_start = None
        group_end = None

        def handle_group():
            nonlocal current_activity, group_start, group_end

            if not current_activity or not group_start or not group_end:
                return

            duration = (group_end - group_start).seconds // 60
            title = body = None

            if current_activity == 1:
                title = "🚶 Bạn đã đi bộ"
                body = f"Từ {group_start.strftime('%H:%M')} đến {group_end.strftime('%H:%M')} vào {date_str}."
            elif current_activity == 2 and duration >= 120:
                title = "⏳ Ngồi quá lâu!"
                body = f"Bạn đã ngồi liên tục {duration // 60} giờ vào {date_str}."
            elif current_activity == 3 and duration >= 30:
                title = "🧍 Bạn đã đứng khá lâu"
                body = f"Đứng khoảng {duration} phút vào {date_str}."
            elif current_activity == 4 and 10 <= duration <= 60:
                title = "🛏️ Nghỉ ngơi hợp lý"
                body = f"Nằm nghỉ {duration} phút vào {date_str}."
            elif current_activity == 5:
                title = "🏃 Tuyệt vời! Bạn đã chạy bộ"
                body = f"Leo cầu thang lúc {group_start.strftime('%H:%M')} vào {date_str}."
            elif current_activity == 7:
                title = "🚴 Bạn đã đạp xe"
                body = f"Đạp xe từ {group_start.strftime('%H:%M')} đến {group_end.strftime('%H:%M')} vào {date_str}."
            elif current_activity == 8:
                title = "⚠️ Phát hiện té ngã!"
                body = f"Té ngã lúc {group_start.strftime('%H:%M')} vào {date_str}. Hãy kiểm tra tình trạng ngay!"

            if title and body:
                send_notification(device_token, title, body)

            current_activity = None
            group_start = None
            group_end = None

        for item in records:
            try:
                activity = int(item['activityType'])
                start = datetime.fromisoformat(item['start_time'])
                end = datetime.fromisoformat(item['end_time'])

                if current_activity is None:
                    current_activity = activity
                    group_start = start
                    group_end = end
                elif activity == current_activity and (start - group_end).seconds <= 20:
                    group_end = end
                else:
                    handle_group()
                    current_activity = activity
                    group_start = start
                    group_end = end
            except Exception as e:
                print("Lỗi khi xử lý record:", e)

        handle_group()  

    if not found_activity_today:
        send_notification(device_token, "📲 Hôm nay bạn thế nào?", "Mở app ngay để xem hành trình hoạt động của bạn hôm nay nhé!")
