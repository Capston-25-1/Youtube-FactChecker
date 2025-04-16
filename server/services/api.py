import google.generativeai as genai
import re
import json
import os
import requests

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model_gemini = genai.GenerativeModel(model_name="gemini-2.0-flash-lite")

GOOGLE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")


def extract_keywords(comment_text):
    prompt = f"""
다음 댓글에서 핵심 키워드 3~6개만 추출해줘.
댓글: "{comment_text}"
응답은 반드시 JSON 형식으로만 작성해줘. 예시:
{{
  "keywords": ["", "", ""],
  "topic": ""
}}
반드시 응답 형식만 반환해
"""
    response = model_gemini.generate_content(prompt)
    raw_output = response.text
    # Markdown 코드 블록 제거
    cleaned = re.sub(r"```json|```", "", raw_output).strip()

    try:
        data = json.loads(cleaned)
        return data.get("keywords", [])
    except Exception as e:
        print("[키워드 추출 JSON 파싱 실패]")
        print("원문:", raw_output)
        return []


def translate_text(text, target_language="en"):
    """
    Google Cloud Translation API를 호출하여 텍스트를 영어로 번역합니다.
    """
    url = (
        f"https://translation.googleapis.com/language/translate/v2?key={GOOGLE_API_KEY}"
    )
    headers = {"Content-Type": "application/json"}
    payload = {"q": text, "target": target_language}

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        translated_text = data["data"]["translations"][0]["translatedText"]
        return translated_text
    else:
        print("번역 API 오류:", response.status_code)
        return None
