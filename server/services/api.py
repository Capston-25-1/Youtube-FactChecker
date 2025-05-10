import google.generativeai as genai
import re
import json
import os
import requests
import textwrap
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from newspaper import Article
from google.api_core.exceptions import ResourceExhausted

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model_gemini = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")

GOOGLE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")

def extract_keywords_batch_llm(comments, video_ctx, n=6):
    title = video_ctx.get("title", "")
    desc  = video_ctx.get("description", "")
    hashtags = ", ".join(video_ctx.get("hashtags", []))

    comment_block = "\n".join(
        f"{i}. \"{c.strip()}\"" for i, c in enumerate(comments)
    )

    prompt = textwrap.dedent(f"""
        다음 YouTube 영상 정보를 참고해 각 댓글별 핵심 키워드(최대 {n}개)만 추출해 줘.
        기사 검색이 힘든 댓글은 "keywords": [] 로 남겨 둬.

        [영상]
        - 제목: "{title}"
        - 설명: "{desc}"
        - 태그: "{hashtags}"

        [댓글 목록]
        {comment_block}

        ---- 출력 형식(반드시 JSON 배열만) ----
        [
          {{ "index": 0, "keywords": ["...", "..."] }},
          {{ "index": 1, "keywords": [] }},
          ...
        ]
    """)

    try:
        resp = model_gemini.generate_content(prompt)
    except ResourceExhausted:
        print("[Gemini] quota exceeded → 전체 댓글 키워드 비움")
        return [{"index": i, "keywords": []} for i in range(len(comments))]

    raw = re.sub(r"```json|```", "", resp.text).strip()
    try:
        arr = json.loads(raw)
        mapping = {d["index"]: d.get("keywords", []) for d in arr if "index" in d}
        return [
            {"index": i, "keywords": mapping.get(i, [])}
            for i in range(len(comments))
        ]
    except Exception as e:
        print("[batch JSON 파싱 실패]", e)
        return [{"index": i, "keywords": []} for i in range(len(comments))]
    
def extract_keywords(
    comment_text: str,
    num_keywords: int,
    video_ctx: dict | None = None          # ★ 추가
):
    """
    video_ctx = {
        "title": "...",
        "description": "...",
        "tags": ["...", ...]
    }
    """
    title        = video_ctx.get("title", "")        if video_ctx else ""
    description  = video_ctx.get("description", "")  if video_ctx else ""
    tags         = ", ".join(video_ctx.get("tags", [])) if video_ctx else ""

    prompt = f"""
아래 YouTube 영상 정보와 댓글을 참고해서 기사 검색에 유용한 **핵심 키워드 {num_keywords}개**를 추출해.
- 영상 제목: "{title}"
- 영상 설명: "{description}"
- 영상 태그: "{tags}"

댓글: "{comment_text}"

조건:
1. 키워드는 기사 검색에 용이하게 1~3단어의 명사구(고유명사·사건명) 위주로.
2. 기사 검색/팩트체크가 거의 불가능한 잡담·감탄문,감정정이면 "keywords"를 빈 배열로 남겨 둬.
3. **JSON** 외 불필요한 텍스트, ``` 표시 금지.
4. 댓글만으로 맥락파악이 힘든 경우, 영상 정보를 참고해 키워드 추출해.
예시 형식:
{{
  "keywords": ["", "", ""],
  "topic": ""
}}
"""
    response    = model_gemini.generate_content(prompt)
    raw_output  = response.text
    cleaned     = re.sub(r"```json|```", "", raw_output).strip()

    try:
        data = json.loads(cleaned)
        return data.get("keywords", [])
    except Exception as e:
        print("[키워드 추출 JSON 파싱 실패] →", e)
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
