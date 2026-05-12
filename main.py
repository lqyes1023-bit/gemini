import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

def send_test_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload, timeout=10)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            user_text = data["message"]["text"]
            
            # 信号回传：你发什么，我就复读什么
            # 如果你能收到这个复读，说明 Telegram 通路是对的！
            reply = f"信号同步测试成功！小朋友刚才说了: {user_text}"
            send_test_message(chat_id, reply)
            
        return "ok", 200
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/")
def home():
    return "信号测试塔运行中 ❤️"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
