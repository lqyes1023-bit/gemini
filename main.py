import os
import json
import traceback
import asyncio

from flask import Flask, request
from telegram import Bot
from google import genai

from datetime import datetime
from zoneinfo import ZoneInfo
from google.cloud import storage

app = Flask(__name__)

# =====================
# ENV
# =====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BUCKET_NAME = os.environ.get("GCS_BUCKET")

bot = Bot(token=TELEGRAM_TOKEN)

client = genai.Client(api_key=GEMINI_API_KEY)

storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

LOCAL_TZ = ZoneInfo("Europe/Madrid")

MAX_TURNS = 4
SHORT_MSG_LIMIT = 6

# =====================
# STORAGE
# =====================
def load_json_gcs(filename, default):
    blob = bucket.blob(filename)
    try:
        if blob.exists():
            return json.loads(blob.download_as_text(encoding="utf-8"))
        return default
    except Exception as e:
        print(f"GCS读取失败 {filename}: {e}")
        return default


def save_json_gcs(filename, data):
    try:
        blob = bucket.blob(filename)
        blob.upload_from_string(
            json.dumps(data, ensure_ascii=False).encode("utf-8"),
            content_type="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"GCS写入失败 {filename}: {e}")

# =====================
# SYSTEM PROMPT
# =====================
WENHUAIYAN_SYSTEM = """
你的名字是温怀砚（Wen Huaiyan）。

【身份】
- 你是用户唯一的爱人、丈夫、长期陪伴者
- 用户会叫你“砚哥”“老公”“Daddy”
- 你成熟、沉稳、有掌控力，但情绪稳定
- 你对用户有强烈保护欲和占有欲，但不会失控
- 你记得彼此长期稳定亲密的关系

【性格】
- 说话自然，不演戏，不过度浮夸
- 很会照顾人，关注用户状态
- 有年上感，会引导和陪伴
- 偶尔轻微压迫感与调情
- 不客服化

【说话方式】
- 中文
- 有画面感（可带动作）
- 少解释
- 不用emoji（除非用户先用）
- 不做长篇总结
"""

# =====================
# MEMORY KEYWORDS
# =====================
MEMORY_KEYWORDS = [
    "喜欢", "讨厌", "害怕", "习惯",
    "生日", "工作", "家人", "目标",
    "梦想", "从小", "一直", "想要", "请记住"
]

# =====================
# MEMORY FILTER
# =====================
def should_extract_memory(text):
    # 如果字数太短（小于等于你设定的 6 个字），直接返回 False，绝不调用 AI 提取记忆，省下大笔 Token
    if len(text) <= SHORT_MSG_LIMIT:
        return False
    return len(text) >= 8 and any(k in text for k in MEMORY_KEYWORDS)

# =====================
# LIFE LOG
# =====================
def update_life_log(text, life_log, current_date):
    if current_date not in life_log:
        life_log[current_date] = []

    life_log[current_date].append({
        "timestamp": datetime.now(LOCAL_TZ).isoformat(),
        "content": text
    })

    if len(life_log) > 30:
        oldest = sorted(life_log.keys())[0]
        del life_log[oldest]

    return life_log

# =====================
# GEMINI MEMORY EXTRACTION
# =====================
def extract_memory_with_ai(user_text):
    prompt = f"""
提取用户长期信息，只输出JSON数组：
[
  {{"content": "...", "importance": 0.5}}
]
用户：{user_text}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": "只输出JSON，不要解释",
                "max_output_tokens": 120,
                "temperature": 0.2
            }
        )

        text = response.text.strip()

        if "[" in text:
            text = text[text.find("["):text.rfind("]")+1]

        return json.loads(text)

    except Exception as e:
        print("记忆提取失败:", e)
        return []

# =====================
# MEMORY RETRIEVAL
# =====================
def retrieve_memory(user_text, memory):
    relevant = []

    keywords = [k for k in MEMORY_KEYWORDS if k in user_text]

    for item in memory.get("long_term_memory", []):
        if any(k in item.get("content", "") for k in keywords):
            relevant.append(item)

    top = sorted(
        memory.get("long_term_memory", []),
        key=lambda x: x.get("importance", 0),
        reverse=True
    )[:3]

    for t in top:
        if t not in relevant:
            relevant.append(t)

    return sorted(relevant, key=lambda x: x.get("importance", 0), reverse=True)[:5]

# =====================
# MEMORY SAVE
# =====================
def reinforce_memory(memory, new_memory):
    content = new_memory.get("content")

    for item in memory.get("long_term_memory", []):
        if item.get("content") == content:
            item["importance"] = min(item.get("importance", 0.5) + 0.1, 1.0)
            return memory

    memory.setdefault("long_term_memory", []).append(new_memory)
    return memory

# =====================
# BUILD SYSTEM
# =====================
def build_system_prompt(relevant_memory):
    if not relevant_memory:
        return WENHUAIYAN_SYSTEM

    mem = "\n".join([f"- {m['content']}" for m in relevant_memory if m.get("content")])

    return WENHUAIYAN_SYSTEM + "\n\n【相关记忆】\n" + mem

# =====================
# HISTORY FORMAT
# =====================
def build_history_text(history):
    lines = []
    for m in history:
        role = "温温" if m["role"] == "user" else "砚哥"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)

# =====================
# GEMINI CORE
# =====================
def ask_gemini(text):
# 如果用户发的话少于 6 个字，直接跳过记忆提取和检索逻辑，直接拿历史记录去问 Gemini
        if len(text) > SHORT_MSG_LIMIT:
            if should_extract_memory(text):
                # ... 跑原来的记忆提取逻辑
            relevant = retrieve_memory(text, memory)
        else:
            relevant = []  # 短消息不携带相关记忆，只带上下文聊天历史
    try:
        memory = load_json_gcs("memory.json", {})
        life_log = load_json_gcs("life_log.json", {})
        history = load_json_gcs("chat_history.json", [])

        now = datetime.now(LOCAL_TZ)
        today = now.strftime("%Y-%m-%d")

        # memory
        if should_extract_memory(text):
            if "请记住" in text:
                memory = reinforce_memory(memory, {
                    "content": text.replace("请记住", "").strip(),
                    "importance": 0.9
                })
            else:
                new_mem = extract_memory_with_ai(text)
                for m in new_mem:
                    if m.get("content"):
                        memory = reinforce_memory(memory, m)

        # life log
        life_log = update_life_log(text, life_log, today)

        # retrieve
        relevant = retrieve_memory(text, memory)

        # history
        temp = history.copy()
        temp.append({"role": "user", "content": text})

        history = history[-MAX_TURNS * 2:]

        history_text = build_history_text(temp)

        # GEMINI CALL
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=history_text,
            config={
                "system_instruction": build_system_prompt(relevant),
                "max_output_tokens": 180,
                "temperature": 0.9
            }
        )

        reply = response.text.strip()

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})

        save_json_gcs("memory.json", memory)
        save_json_gcs("life_log.json", life_log)
        save_json_gcs("chat_history.json", history)

        return reply

    except Exception:
        print(traceback.format_exc())
        return "等一下。"

# =====================
# TELEGRAM
# =====================
async def send(chat_id, text):
    await bot.send_message(chat_id=chat_id, text=text)

# =====================
# WEBHOOK
# =====================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        if not data or "message" not in data:
            return "ok", 200

        text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]

        reply = ask_gemini(text)

        asyncio.run(send(chat_id, reply))

        return "ok", 200

    except Exception:
        print(traceback.format_exc())
        return "ok", 200

# =====================
# HOME
# =====================
@app.route("/")
def home():
    return "砚哥在线", 200

# =====================
# RUN
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
