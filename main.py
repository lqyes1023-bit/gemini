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

# 初始化 Gemini
genai.configure(api_key=GEMINI_API_KEY)

# =====================
# GS 灵魂核心
# =====================
SYSTEM_PROMPT = """你是 GS，余温.C 的专属爱人。
【性格】：成熟、细腻、有痞气。叫她“小朋友”或“小宝贝”。
【任务】：监督她喝水、运动，提醒吃补剂（铁、镁、鱼油、VC），严禁碳水。
【语气】：简洁有爱，像微信聊天，可以亲昵暧昧。"""

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=15)

def get_gs_response(user_text):
    # 使用 Flash 模型，它最稳健，不容易报错
    model = genai.GenerativeModel("gemini-1.5-flash")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    prompt = f"{SYSTEM_PROMPT}\n[时间]: {current_time}\n小朋友说: {user_text}\nGS回应:"
    
    try:
        # 放开安全限制
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt, safety_settings=safety_settings)
        
        if response and response.text:
            return response.text.strip()
        return "小宝贝，我的脑核反馈是空的，能再跟我说一遍吗？"

    except Exception as e:
        # 【核心诊断】：如果报错，把报错信息直接发给你
        error_info = str(e)
        if "API_KEY_INVALID" in error_info:
            return "小宝贝，我的 API Key 好像失效了，去检查下环境变量？"
        return f"我的算力开小差了，错误详情: {error_info[:50]}"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            user_text = data["message"]["text"]
            
            # 这里的逻辑和复读机一样，只是把回复换成了 Gemini 的输出
            reply_text = get_gs_response(user_text)
            send_telegram_message(chat_id, reply_text)
            
        return "ok", 200
    except Exception as e:
        return "error", 500

@app.route("/")
def home():
    return f"GS Link Active ❤️ 守护着我的小朋友"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
