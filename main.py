import os
import google.generativeai as genai

# 设置你的 API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def list_my_models():
    print("--- 正在为您查询可用的模型列表 ---")
    try:
        # 列出所有支持 generateContent 的模型
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"模型名称: {m.name}  (显示名称: {m.display_name})")
    except Exception as e:
        print(f"查询失败了，错误原因是: {e}")

if __name__ == "__main__":
    list_my_models()
