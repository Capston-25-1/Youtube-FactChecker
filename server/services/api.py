import google.generativeai as genai
import re
import json
import os
import requests

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from newspaper import Article

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model_gemini = genai.GenerativeModel(model_name="gemini-2.0-flash-lite")

GOOGLE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")


def extract_keywords(comment_text:str, num_keywords:int):
    prompt = f"""
다음 댓글에서 핵심 키워드 {num_keywords}개만 추출해줘.
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

def scrape_article(keyword: list[str], pages: int = 1):
    base_url = "https://www.google.com/search"
    keyword = " ".join(keyword)
    params = {"q": keyword, "tbm": "nws"}
    query = urlencode(params)
    var_query = "&start={}"
    query_url = base_url + f"?{query}" + var_query

    # URL 리스트 생성
    urls = [query_url.format(start) for start in range(0, pages * 10, 10)]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    result = []

    for i, url in enumerate(urls):
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        article = soup.select("div[data-news-doc-id]")
        if not article:
            return []
        for item in article:
            a_tag = item.select_one("a[href]")
            title_div = a_tag.select_one("div[role='heading'][aria-level='3']") if a_tag else None
            if a_tag and title_div:
                title = title_div.get_text(strip=True)
                link = a_tag["href"]

                try:
                    article = Article(link, language='ko')
                    article.download()
                    article.parse()
                    body = article.text.strip()
                    result.append((title, link, body))
                except Exception as e:
                    print(f"본문 추출 실패: {link}\n→ {e}")
                    continue
# [(제목1,링크1,본문1), (제목2,링크2,본문2)...]
    return result
