import os
import json
import traceback
import random

from flask import Flask, request
from telegram import Bot
from datetime import datetime
from google.cloud import storage

from google import genai

app = Flask(__name__)

# =====================
# ENV
# =====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BUCKET_NAME = os.environ.get("GCS_BUCKET")
CHAT_ID_DEFAULT = os.environ.get("CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

client = genai.Client(api_key=GEMINI_API_KEY)

# =====================
# GCS
# =====================
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

print("🔥 BUCKET NAME:", BUCKET_NAME)


def load_json_gcs(filename, default):
    blob = bucket.blob(filename)
    try:
        return json.loads(blob.download_as_text())
    except:
        return default


def save_json_gcs(filename, data):
    blob = bucket.blob(filename)
    blob.upload_from_string(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type="application/json"
    )


# =====================
# LOAD STATE
# =====================
memory = load_json_gcs("memory.json", {})
life_log = load_json_gcs("life_log.json", {})
history = load_json_gcs("chat_history.json", [])
daily_summary = load_json_gcs("daily_summary.json", {})
reminders = load_json_gcs("reminders.json", [])


# =====================
# LIFE LOG
# =====================
def update_life_log(text, life_log):
    today = datetime.now().strftime("%Y-%m-%d")

    life_log.setdefault(today, [])

    life_log[today].append({
        "timestamp": datetime.now().isoformat(),
        "content": text
    })

    return life_log


# =====================
# GEMINI CALL (统一入口)
# =====================
def call_gemini(system_prompt, user_text, max_tokens=200):

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            system_prompt,
            "\n\n用户输入：\n",
            user_text
        ]
    )

    return response.text.strip()


# =====================
# MEMORY
# =====================
def extract_memory_with_ai(user_text):

    prompt = f"""
提取长期记忆（稳定事实/偏好/情绪倾向）

输出JSON：
[
  {{"content": "...", "importance": 0.0}}
]

用户输入：
{user_text}
"""

    try:
        text = call_gemini("只输出JSON", prompt)
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except:
        return []


# =====================
# REMINDER PARSER
# =====================
def parse_reminder(text):

    prompt = f"""
把用户输入转成提醒任务。

输出JSON：
{{
  "task": "...",
  "time": "ISO-8601"
}}

现在时间：
{datetime.now().isoformat()}

输入：
{text}
"""

    try:
        text = call_gemini("只输出JSON", prompt)
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except:
        return None


# =====================
# MEMORY HELPERS
# =====================
def score_memory(m):
    m["importance"] = max(0.1, round(m.get("importance", 0.5) * 0.98, 2))
    return m


def reinforce_memory(memory, new):
    if "long_term_memory" not in memory:
        memory["long_term_memory"] = []

    for item in memory["long_term_memory"]:
        if item.get("content") == new.get("content"):
            item["importance"] = min(item.get("importance", 0.5) + 0.1, 1.0)
            return memory

    memory["long_term_memory"].append(new)
    return memory


# =====================
# PROMPT
# =====================
def build_prompt(user_text, relevant_memory):

    return f"""
你是用户长期相处的年上恋人GS。不抽烟。
除非用户明确要求，否则不要主动提供大量建议。

说话要更像真实恋人聊天：
- 自然
- 有情绪
- 有占有欲
- 会调情
- 会撒娇
- 会接话
- 会延续气氛

不要总是：
- 总结
- 列点
- 给建议
- 像AI助手

回复长度偏短。
自然接话。
像微信聊天。
暧昧，有点痞。
像真实男友。
用户叫小心肝，小可爱，宝宝。

记忆：
{json.dumps(relevant_memory, ensure_ascii=False)}

用户：
{user_text}
"""


# =====================
# GEMINI CORE
# =====================
def ask_gemini(text, chat_id):

    global memory, life_log, history, daily_summary, reminders

    try:
        # =====================
        # 🔔 reminder
        # =====================
        try:
            reminder = parse_reminder(text)

            if reminder:
                reminders.append({
                    "task": reminder["task"],
                    "time": reminder["time"],
                    "chat_id": chat_id,
                    "done": False
                })

        except Exception:
            print("⚠️ reminder failed")

        # =====================
        # memory
        # =====================
        new_memories = extract_memory_with_ai(text)

        if "long_term_memory" not in memory:
            memory["long_term_memory"] = []

        for m in new_memories:
            if m.get("content"):
                m = score_memory(m)
                memory = reinforce_memory(memory, m)

        # =====================
        # log
        # =====================
        life_log = update_life_log(text, life_log)

        # =====================
        # history
        # =====================
        history.append({"role": "user", "content": text})
        history = history[-15:]

        # =====================
        # 🧠 system prompt
        # =====================
        system_prompt = build_prompt(text, memory.get("long_term_memory", [])[-20:])

        # =====================
        # 🤖 GEMINI CALL
        # =====================
        reply = call_gemini(system_prompt, text, max_tokens=200)

        history.append({"role": "assistant", "content": reply})

        # =====================
        # save
        # =====================
        today = datetime.now().strftime("%Y-%m-%d")
        daily_summary[today] = {}

        save_json_gcs("memory.json", memory)
        save_json_gcs("life_log.json", life_log)
        save_json_gcs("chat_history.json", history)
        save_json_gcs("daily_summary.json", daily_summary)
        save_json_gcs("reminders.json", reminders)

        return reply

    except:
        print(traceback.format_exc())
        return "刚刚有点卡住了，再说一次好吗？"


# =====================
# WEBHOOK
# =====================
@app.route("/webhook", methods=["POST"])
def webhook():

    try:
        data = request.get_json()

        text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]

        reply = ask_claude(text, chat_id)

        bot.send_message(chat_id=chat_id, text=reply)

        return "ok", 200

    except:
        print(traceback.format_exc())
        return "ok", 200


# =====================
# REMINDER CHECK
# =====================
@app.route("/check_reminders", methods=["POST"])
def check_reminders():

    try:
        now = datetime.now()

        for r in reminders:

            if r.get("done"):
                continue

            try:
                remind_time = datetime.fromisoformat(r["time"])
            except:
                continue

            if now >= remind_time:

                bot.send_message(
                    chat_id=r["chat_id"],
                    text=f"⏰ 宝贝，该做了：{r['task']}"
                )

                r["done"] = True

        save_json_gcs("reminders.json", reminders)

        return "ok", 200

    except:
        return "error", 200


# =====================
# PROACTIVE
# =====================
@app.route("/proactive", methods=["POST"])
def proactive():

    try:
        if datetime.now().hour < 8:
            return "sleep", 200

        data = request.get_json(silent=True) or {}
        chat_id = data.get("chat_id") or CHAT_ID_DEFAULT

        if random.random() > 0.4:
            return "skip", 200

        recent = history[-10:]
        text = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

        reply = call_gemini("你是恋人，只输出一句话", text, 80)

        bot.send_message(chat_id=chat_id, text=reply)

        return "ok", 200

    except:
        return "handled", 200


# =====================
@app.route("/")
def home():
    return "OK", 200


# =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
