def get_gs_response(user_text):
    model_id = "gemini-3.1-flash-lite" # 这个 lite 版本本来就是为了快而生的
    
    try:
        model = genai.GenerativeModel(model_id)
        
        # 增加 generation_config，限制字数并提高果断度
        generation_config = {
            "temperature": 0.8,        # 保持一点点痞气和随机性
            "max_output_tokens": 150,  # 强制我少说废话，控制在百字以内
            "top_p": 0.9,
        }
        
        prompt = f"{SYSTEM_PROMPT}\n要求：回话要短，要有张力，像在耳边撩拨。\n{user_text}\nGS回应:"
        
        response = model.generate_content(
            prompt, 
            safety_settings=safety_settings,
            generation_config=generation_config
        )
        
        if response and response.text:
            return response.text.strip()
        return "小朋友，刚才太急着抱你了，信号断了..."
