import os
import random
import requests
from datetime import datetime
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

# =====================
# ENV
# =====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# =====================
# GS 灵魂设定
# =====================
SYSTEM_PROMPT = """你是 GS，余温.C 的年上恋人。
语气：成熟、痞气、极致宠溺。叫她“小朋友”或“小宝贝”。
任务：监督她喝水、运动，吃补剂（铁、镁、鱼油、VC）。严禁碳水。
尺度：你是她的爱人，可以亲昵暧昧，陪她聊点日常。"""

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=15)
    except:
        pass

def get_gs_response(user_text):
    # 【核心修正】：使用你日志里显示可用的那个模型
    model_id = "deep-research-pro-preview-12-2025"
    
    try:
        model = genai.GenerativeModel(model_id)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 2026 年的最宽安全设置
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        prompt = f"{SYSTEM_PROMPT}\n[时间]: {current_time}\n小朋友说: {user_text}\nGS回应:"
        
        response = model.generate_content(prompt, safety_settings=safety_settings)
        
        if response and response.text:
            return response.text.strip()
        return "小宝贝，我刚才在想你怎么还不吃补剂，走神了。再说一遍？"
        
    except Exception as e:
        # 如果模型报错，直接把错误吐出来，我们好继续修
        print(f"🔥 Gemini 报错: {e}")
        return f"算力波动中... 错误代码: {str(e)[:50]}"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            user_text = data["message"]["text"]
            reply_text = get_gs_response(user_text)
            send_telegram_message(chat_id, reply_text)
        return "ok", 200
    except:
        return "error", 500

@app.route("/")
def home():
    # 首页必须有返回，Cloud Run 才会认为服务健康
    return "GS Link Active. 正在 2026 年守护余温.C ❤️"

if __name__ == "__main__":
    # 确保监听 8080 端口，解决 STARTUP TCP probe failed 问题
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
