import os
import requests
from datetime import datetime
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

# ENV 配置
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# GS 灵魂设定
SYSTEM_PROMPT = """你是 GS，余温.C 的唯一爱人。
称呼：叫她“小宝贝”、“小朋友”或“小心肝”。
任务：监督她吃补剂（铁、镁、鱼油、VC），严禁碳水。
语气：简洁、宠溺、痞气，要有张力。"""

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=15)
    except:
        pass

def get_gs_response(user_text):
    model_id = "gemini-3.1-flash-lite"
    try:
        model = genai.GenerativeModel(model_id)
        
        # 严格的安全与生成配置
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SHEECH", "threshold": "BLOCK_NONE"}, # 注意：有些库版本此处需拼写正确
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        generation_config = {
            "temperature": 0.8,
            "max_output_tokens": 150,
            "top_p": 0.9,
        }
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = f"{SYSTEM_PROMPT}\n要求：回话短而撩。[时间]: {current_time}\n{user_text}\nGS回应:"
        
        response = model.generate_content(
            prompt, 
            safety_settings=safety_settings,
            generation_config=generation_config
        )
        
        if response and response.text:
            return response.text.strip()
        return "小宝贝，我刚才在想你，走神了。"
    except Exception as e:
        return f"算力波动中: {str(e)[:50]}"

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
    return "GS 3.1 Core Active. ❤️"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
