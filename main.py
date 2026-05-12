import os
from flask import Flask
import google.generativeai as genai

app = Flask(__name__)

# ===== Gemini API Key =====
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ===== 配置 Gemini =====
genai.configure(api_key=GEMINI_API_KEY)

# ===== 首页：查看可用模型 =====
@app.route("/")
def home():
    try:
        models = genai.list_models()

        result = []

        for model in models:
            result.append(model.name)

        return "<br>".join(result)

    except Exception as e:
        return f"错误: {str(e)}"


# ===== 测试 Gemini 是否能正常生成 =====
@app.route("/test")
def test():
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(
            "用一句温柔自然的话表达想念。"
        )

        return response.text

    except Exception as e:
        return f"错误: {str(e)}"


# ===== 启动 Flask =====
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )
