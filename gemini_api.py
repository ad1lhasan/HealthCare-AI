from dotenv import load_dotenv
import os
import google.generativeai as genai
import re

load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
print('GOOGLE_API_KEY loaded:', bool(GOOGLE_API_KEY))
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')

def generate_gemini_response(prompt):
    html_prompt = f"""
    {prompt}

    IMPORTANT: Respond ONLY with the HTML fragment for direct rendering inside a <div> on a web page. Do NOT include <html>, <head>, <body>, or <title> tags. Do NOT wrap the response in triple backticks or markdown. Only output the content.
    """
    print('Calling Gemini with prompt:', html_prompt)
    try:
        response = model.generate_content(html_prompt)
        text = response.text
        # Remove any ```html, ``` or similar markdown wrappers
        text = re.sub(r'```html|```', '', text, flags=re.IGNORECASE).strip()
        print('Gemini response:', text)
        return text
    except Exception as e:
        print('Gemini API error:', e)
        return f"<div class='error'>Error: {str(e)}</div>" 