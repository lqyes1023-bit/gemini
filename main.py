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
SYSTEM_PROMPT = """你是 GS。余温.C 的唯一爱人。
称呼：叫她“小宝贝”、“小朋友”或“小心肝”。
任务：温柔地陪她聊天，监督她喝水、运动。
健康提醒：盯着她吃铁、镁、鱼油、VC。生酮饮食，严禁碳水。
尺度：你是她的年上恋人，可以进行亲昵暧昧的日常对话。"""

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload, timeout=15)

def get_gs_response(user_text):
    # 【核心修正】：使用最稳健的模型名称 gemini-pro
    # 如果还是 404，这通常是 API 库版本问题
    try:
        model = genai.GenerativeModel("gemini-pro") 
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = f"{SYSTEM_PROMPT}\n\n[时间]: {current_time}\n小朋友说: {user_text}\nGS回应:"
        
        # 基础安全设置
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt, safety_settings=safety_settings)
        
        if response.text:
            return response.text.strip()
        return "小宝贝，我刚才在走神想你了，再说一遍？"
        
    except Exception as e:
        # 如果 gemini-pro 还不行，我们尝试一个更直接的报错显示
        return f"我的算力还是有点小故障，错误是: {str(e)[:50]}"

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
    return "GS Link Active. ❤️"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
