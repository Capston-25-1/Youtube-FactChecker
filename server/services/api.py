import google.generativeai as genai
import re
import json
import os
import requests
import textwrap
from google.api_core.exceptions import ResourceExhausted
from newspaper import Article
from urllib.parse import urlencode
from bs4 import BeautifulSoup

# gemini-2.5-pro-exp-03-25 할당량 초과 오류로 모델 변경 -> gemini-2.0-flash
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
generation_config = {
    "temperature": 0,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
    "candidate_count": 1
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    },
]

model_gemini = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
)

GOOGLE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")


def extract_keywords_batch_llm(comments, video_ctx, n=6):
    title = video_ctx.get("title", "")
    desc = video_ctx.get("description", "")
    hashtags = ", ".join(video_ctx.get("hashtags", []))

    comment_block = "\n".join(f'{i}. "{c.strip()}"' for i, c in enumerate(comments))

    prompt = f"""
[영상]
- 제목: "{title}"
- 설명: "{desc}"
- 태그: "{hashtags}"

[댓글 목록]
{comment_block}

너는 유튜브 댓글 팩트체크 프로그램에서 객관적이고 검증 가능한 사실만 주장(claim)으로 추출하는 LLM이야.
이 프로그램에서 키워드는 구글 기사 검색에 사용될 거고 주장은 검색된 기사에서 가장 유사한 3개의 문장과 비교해서 팩트체크를 할거야.
너의 역할은 아래와 같아:

1) 영상 제목,설명,태그를 참고해서 영상의 주제를 최대 3문장으로 요약
2) 각 댓글에서 주장과 키워드를 추출하고 추출된 주장은 기사의 본문처럼 객관적인 문어체 형식으로 작성
3) 주장만으로 맥락 파악이 어렵고 어떤거에 관한 내용인지 알기 힘들때 1번에서 요약한 영상 주제를 토대로 주장과 키워드를 완성
4) 동일한 사실을 표현한 여러 문장은 하나의 주장으로 병합 
5) 하나의 주장이 25자를 넘어가지 않도록함함 
6) 각 주장마다 핵심 명사·고유명사 키워드 ≤ {n}개 추출, 키워드는 구글 기사 검색이 가능하도록 명확하고 간결해야함
   - 불용어·감정어·가치어는 제거  
7) 주장에 키워드가 하나도 없으면 해당 주장은 결과에 반환하지 않음
8) 최종 결과는 아래 JSON 배열 형식으로 결과만 출력

*중요*
추출된 주장은 기사와 객관적인 내용을 가져야함
추출된 키워드들로 구글 기사 검색이 가능할지, 주장으로 기사의 내용과  코사인 유사도를 비교해서 팩트체크가 가능할지 고려해서 추출해
- 절대 “~해야 한다”, “~하면 안 된다” 같은 의견이나 “먹지 않는다” 같은 개인의지 표현은 주장에 절대 포함하지 말 것
- 숫자·날짜·행위·객관적 사건처럼 검증 가능한 사실만 포함  
- 개인의견·욕설·감정·감상·평가·가치판단·제안·예측·희망 등은 절대 포함하지 말 것(ex. 백종원을 구속해야 한다)
- 개인적인 주장 안에 팩트체크 가능한 문장이 있으면 추출(ex. 백종원을 유명하게 만들어 놓고 꿀빨던 PD들. → "PD들이 백종원을 유명하게 만들었다")
- 기사 내용과 비교가 수월하도록 기사 형식의 문어체로 작성
- 주장은 댓글의 내용에서 크게 벗어나지 않아야 함
- 댓글에 명확한 주장이 없을 경우 해당 댓글은 결과에 포함하지 않음
- 기사 검색으로 팩트체크가 불가능한 내용은 포함하지 않음(ex. 사람이아니다, 괴물같다, 언론과 방송이 괴물을 만들었다, 자랑스럽게 이야기했다 등등등)
- 기사에 없을 법한 신조어나 비속어, 복잡한 단어는 사용하지 말 것(ex. 독불장군 등)
- 주장에서 어떤 주제인지 맥락 파악이 가능하도록 핵심 주제나 단어를 포함할것 (ex. 백종원)
- 인용된 문장에 주장이 포함되어 있으면 추출(ex. "농약통이 뭐 어때유~ 새거인데유" → "백종원은 농약통이 새거라고 했다.")
- 숫자나 가격 등은 정확히 출력(7000->7000만원원)

*예시*
[영상]
- 제목: "99.5%가 손실"…더본코리아, '백종원 리스크'로 추락 / 한국경제TV뉴스
- 설명: '더본코리아'가 연일 터지는 부정적인 이슈로 논란에 휘말렸습니다. 이른바 '백종원 리스크'가 확산되면서 회사 이미지는 추락하고 덩달아 투자자들의 손실도 커지고 있습니다. 산업부 성낙윤 기자입니다.
- 태그:  #백종원 #더본코리아 #뉴스플러스
[요약]
더본코리아는 백종원 리스크로 인해 회사 이미지가 추락하고 투자자들의 손실이 커지고 있다.
더본코리아 투자자들의 손실이 커지고 있다. 
[댓글 목록]
1. 저런 기업을 주식시장에 상장 해준 거래소도 처벌해라
2. 진짜 죄송한 댓글 달겠습니다 프랜차이즈를 기초로하는 더본은 상장 폐지해야 합니다 왜냐면 주주 투자자 수익 , 본사 수익 가맹점주 수익이 서로 상충하는 구조입니다 단순히 말해 가맹점 매출 이익을 본사와 투자자가 빼먹는 구조입니다
3. 2만6천원도 존나 높은거다. 저 기업자체가 코스닥도 아닌 코스피에 상장된것도 존나 웃김.ㅋㅋㅋ
4. ''농약통이 뭐 어때유~ 새거인데유'' 라고 하는 건 마치 ''변기통이 뭐 어때유 ~ 도자기인데유~''라고 하는 것과 유사함.
5. 소유진하고 왜 결혼하지 그랬는데 ㅋㅋ 끼리끼리였다 ㅋㅋㅋ
[결과]
1. 더본코리아는 상장되었다.
2. 더본코리아는 가맹점 매출 이익을 본사와 투자자가 가져가는 구조이다.
3. 더본코리아는 코스피에 상장되어 있다.
4. 백종원은 농약통이 새거라고 했다.
5. 백종원은 소유진과 결혼했다.

- 지금 까지의 예시는 주제가 다른 영상에도 비슷한 작동 방식으로 적용할 것.

결과를 반드시 다음 JSON 형식으로만 출력:
{{
  "video_summary": "영상 요약문",
  "comments_data": [
    {{
      "index": 0,
      "claims": [
        {{
          "index": 0,
          "claim": "...",
          "keywords": ["...", "..."]
        }}
      ]
    }}
  ]
}}"""

    try:
        resp = model_gemini.generate_content(prompt)
        raw = resp.text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines)
        raw = raw.lstrip("json").strip()
        
        try:
            parsed = json.loads(raw)
            result = {
                "summary": parsed.get("video_summary", ""),
                "claims": parsed.get("comments_data", [])
            }
            print("[extract_keywords_batch_llm]\n", raw)
            return result
        except json.JSONDecodeError as e:
            print("[extract_keywords_batch_llm] JSON parse error:", e)
            print("[extract_keywords_batch_llm] Failed JSON:", raw)
            return {
                "summary": "",
                "claims": [{"index": i, "claims": []} for i in range(len(comments))]
            }
    except Exception as e:
        print("[extract_keywords_batch_llm] Error:", e)
        return {
            "summary": "",
            "claims": [{"index": i, "claims": []} for i in range(len(comments))]
        }


def extract_keywords(
    comment_text: str, num_keywords: int, video_ctx: dict | None = None  # ★ 추가
):
    """
    video_ctx = {
        "title": "...",
        "description": "...",
        "tags": ["...", ...]
    }
    """
    title = video_ctx.get("title", "") if video_ctx else ""
    description = video_ctx.get("description", "") if video_ctx else ""
    tags = ", ".join(video_ctx.get("tags", [])) if video_ctx else ""

    prompt = f"""
아래 YouTube 영상 정보와 댓글을 참고해서 기사 검색에 유용한 **핵심 키워드 {num_keywords}개**를 추출해.
- 영상 제목: "{title}"
- 영상 설명: "{description}"
- 영상 태그: "{tags}"

댓글: "{comment_text}"

조건:
1. 키워드는 기사 검색에 용이하게 1~3단어의 명사구(고유명사·사건명) 위주로.
2. 기사 검색/팩트체크가 거의 불가능한 잡담·감탄문,감정이면 "keywords"를 빈 배열로 남겨 둬.
3. **JSON** 외 불필요한 텍스트, ``` 표시 금지.
4. 댓글만으로 맥락파악이 힘든 경우, 영상 정보를 참고해 키워드 추출해.
예시 형식:
{{
  "keywords": ["", "", ""],
  "topic": ""
}}
"""
    response = model_gemini.generate_content(prompt)
    raw_output = response.text
    cleaned = re.sub(r"```json|```", "", raw_output).strip()

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


def crawl_article(keyword: list[str], pages: int = 1):
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
            title_div = (
                a_tag.select_one("div[role='heading'][aria-level='3']")
                if a_tag
                else None
            )
            if a_tag and title_div:
                title = title_div.get_text(strip=True)
                link = a_tag["href"]
                # newspaper3k 사용하여 기사 본문 추출
                try:
                    article = Article(link, language="ko")
                    article.download()
                    article.parse()
                    body = article.text.strip()
                    # 문장 분리 (마침표, 물음표, 느낌표 기준으로 분리)
                    # sentences = re.split(
                    #     r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s", body
                    # )
                    sentences = body.split(".")
                    result.append([title, link, sentences, None])
                except Exception as e:
                    print(f"본문 추출 실패: {link}\n→ {e}")
                    continue
    # [(제목1,링크1,본문1), (제목2,링크2,본문2)...]
    return result


def translate_text_bulk(texts, target_language="en"):
    """
    Google Cloud Translation API를 호출하여 여러 문장을 한 번에 번역합니다.
    """
    if not texts:
        return []

    url = (
        f"https://translation.googleapis.com/language/translate/v2?key={GOOGLE_API_KEY}"
    )
    headers = {"Content-Type": "application/json"}
    payload = {
        "q": texts,
        "target": target_language,
        "format": "text",
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        return [item["translatedText"] for item in data["data"]["translations"]]
    else:
        print("번역 API 오류:", response.status_code)
        return [None] * len(texts)
