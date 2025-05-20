import google.generativeai as genai
import re
import json
import os
import requests
import textwrap
from google.api_core.exceptions import ResourceExhausted

# gemini-2.5-pro-exp-03-25 할당량 초과 오류로 모델 변경 -> gemini-2.0-flash
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model_gemini = genai.GenerativeModel(model_name="gemini-2.0-flash")

GOOGLE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY")

def extract_keywords_batch_llm(comments, video_ctx, n=6):
    title = video_ctx.get("title", "")
    desc  = video_ctx.get("description", "")
    hashtags = ", ".join(video_ctx.get("hashtags", []))

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
2. 기사 검색/팩트체크가 거의 불가능한 잡담·감탄문,감정이면 "keywords"를 빈 배열로 남겨 둬.
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
