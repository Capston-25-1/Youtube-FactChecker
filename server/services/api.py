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
model_gemini = genai.GenerativeModel(model_name="gemini-2.0-flash")

GOOGLE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")

#여러 댓글들에 대해 주장 분리 및 키워드 추출
def extract_keywords_batch_llm(comments, video_ctx, n=6):
    title    = video_ctx.get("title", "")
    desc     = video_ctx.get("description", "")
    hashtags = ", ".join(video_ctx.get("hashtags", []))

    # 전체 댓글을 한 번에 처리하는 배치 프롬프트
    comment_block = "\n".join(
        f'{i}. "{c.strip()}"' for i, c in enumerate(comments)
    )

    prompt = f"""
[영상]
- 제목: "{title}"
- 설명: "{desc}"
- 태그: "{hashtags}"

[댓글 목록]
{comment_block}

각 댓글마다:
0) 문장 구조를 분석해서 “주어(+보어)와 동사”가 2개 이상 반복되면 독립된 주장으로 간주
1) 기사 검색으로 팩트체크 불가능한 주장은 제외
    ex) [영상]
    - 제목: "뉴스 브리핑: 트럼프, 대선 출마 선언"
    - 설명: "전직 대통령 도널드 트럼프가 2025년 대선 출마를 공식 선언했습니다. 주요 발언과 반응을 담은 리포트입니다."
    - 태그: "트럼프, 대선, 미국정치, 선거, 정책"
    댓글: "트럼프는 세금을 내지 않으려고 했고 그의 정책은 환경을 파괴한다"
    -> 주장1: "트럼프는 세금을 내지 않으려고 했다" 
    -> 주장2: "트럼프의 정책은 환경을 파괴한다"
2) 댓글에 주장이 한 개라면 그대로 사용
3) 각 주장별로 기사 검색에 유용한 키워드 최대{n}개 추출
4) 주장이 기사 검색으로 팩트체크가 불가능하면, 키워드는 빈칸으로 남겨둬
5) 키워드가 추출되지 않은 주장은 결과에 반환하지 않음

결과를 반드시 다음 JSON 배열 형식으로 결과만 출력해줘:
[
  {{
    "index": 0,             # 댓글 인덱스
    "claims": [
      {{
        "index": 0,         # 댓글 내 주장 인덱스
        "claim": "...",
        "keywords": ["...", "..."]
      }},
      ...
    ]
  }},
  ...
]
"""
    # 호출 및 예외 처리
    try:
        resp = model_gemini.generate_content(prompt)
    except ResourceExhausted as e:
        print("[extract_keywords_batch_llm] Quota exhausted:", e)
        return [{"index": i, "claims": []} for i in range(len(comments))]

    raw = resp.text.strip()
    # 코드블록 백틱 및 마크다운 제거
    if raw.startswith("```"):
        lines = raw.splitlines()
        # 첫 백틱 라인 제거
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # 마지막 백틱 라인 제거
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines)
    # 마크다운 언어 태그 제거 (예: json)
    raw = raw.lstrip("json").strip()

    print("[extract_keywords_batch_llm] cleaned raw:", raw)

    try:
        parsed = json.loads(raw)
        return parsed
    except json.JSONDecodeError as e:
        print("[extract_keywords_batch_llm] JSON parse error:", e)
        return [{"index": i, "claims": []} for i in range(len(comments))]
    
# 단일 댓글에 대해 주장 분리 및 키워드 추출
def extract_keywords(
    comment_text: str,
    num_keywords: int,
    video_ctx: dict | None = None
) -> list[dict]:
    """
    [
        {
            "claim": "첫 번째 주장",
            "keywords": [
                "키워드1",
                "키워드2",
                "키워드3"
            ]
        },
        {
            "claim": "두 번째 주장",
            "keywords": [
                "키워드A",
                "키워드B"
            ]
        }
    ]
    """
    title        = video_ctx.get("title", "")        if video_ctx else ""
    description  = video_ctx.get("description", "")  if video_ctx else ""
    tags         = ", ".join(video_ctx.get("tags", [])) if video_ctx else ""

    prompt = f"""
[영상]
- 제목: "{title}"
- 설명: "{description}"
- 태그: "{tags}"

댓글: "{comment_text}"

이 댓글에 대해:
0) 문장 구조를 분석해서 “주어(+보어)와 동사”가 2개 이상 반복되면 독립된 주장으로 간주
1) 기사 검색으로 팩트체크 불가능한 주장은 제외
2) 댓글 만으로 주장 파악이 힘들 경우 영상 정보를 활용
3) 각 주장별로 기사 검색에 유용한 핵심 키워드 최대{num_keywords}개 추출
4) 키워드가 추출되지 않은 주장은 결과에 반환하지 않음
    ex) [영상]
    - 제목: "뉴스 브리핑: 트럼프, 대선 출마 선언"
    - 설명: "전직 대통령 도널드 트럼프가 2025년 대선 출마를 공식 선언했습니다. 주요 발언과 반응을 담은 리포트입니다."
    - 태그: "트럼프, 대선, 미국정치, 선거, 정책"
    댓글: "트럼프는 세금을 내지 않으려고 했고 그의 정책은 환경을 파괴한다"
    -> 주장1: "트럼프는 세금을 내지 않으려고 했다" 
    -> 주장2: "트럼프의 정책은 환경을 파괴한다"

결과를 반드시 다음 JSON 배열만 반환해줘:
[
  {{
    "claim": "첫 번째 주장",
    "keywords": ["키워드1", "키워드2"]
  }},
  ...
]
"""
    try:
        resp = model_gemini.generate_content(prompt)
    except Exception:
        return [{"claim": comment_text, "keywords": []}]

    # 1) 원본 응답 텍스트 가져오기 & strip
    raw = resp.text.strip()

    # 2) ```…``` 코드블록 제거
    if raw.startswith("```"):
        lines = raw.splitlines()
        # 첫/마지막 백틱 줄 제거
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines)

    # 3) 언어 태그(json) 제거
    raw = raw.lstrip("json").strip()

    # 4) JSON 파싱
    try:
        batch = json.loads(raw)
    except json.JSONDecodeError:
        return [{"claim": comment_text, "keywords": []}]

    return [
        {"claim": item["claim"], "keywords": item.get("keywords", [])}
        for item in batch
        if "claim" in item
    ]



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
