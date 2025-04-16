import os
import re
import json
import asyncio
import aiohttp
import nltk
import torch
from sentence_transformers import SentenceTransformer, util
import google.generativeai as genai

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from newspaper import Article

# nltk punkt tokenizer (최초 한 번 실행)
nltk.download('punkt')

# 1. 키워드 추출
genai.configure(api_key="YOUR_GEMINI_API_KEY")
model_gemini = genai.GenerativeModel(model_name="models/gemini-1.5-pro-latest")

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

# 2. 기사 크롤링
def scrape_article(keyword: str, pages: int = 1):
    base_url = "https://www.google.com/search"
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

        for item in soup.select("div[data-news-doc-id]"):
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

# 3. 기사 내 유사 문장 추출 (SentenceTransformer 활용)
def extract_similar_sentences(article_text, comment, top_k=3):
    """
    기사 본문을 문장 단위로 분할하고, 댓글과 유사한 top_k 문장을 추출합니다.
    """
    sentences = nltk.tokenize.sent_tokenize(article_text)
    if not sentences:
        return []
    
    transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # 임베딩 계산
    sentence_embeddings = transformer_model.encode(sentences, convert_to_tensor=True)
    comment_embedding = transformer_model.encode(comment, convert_to_tensor=True)
    
    # 코사인 유사도 계산
    cosine_scores = util.cos_sim(comment_embedding, sentence_embeddings)[0]
    
    # 상위 top_k 문장 선택
    top_results = torch.topk(cosine_scores, k=top_k)
    similar_sentences = [sentences[idx] for idx in top_results[1].tolist()]
    return similar_sentences

# 4. Google Cloud Translation API를 통한 비동기 영어 번역 함수
GOOGLE_API_KEY = os.environ.get("GOOGLE_CLOUD_TRANSLATION_API_KEY", "YOUR_GOOGLE_TRANSLATION_API_KEY")

async def translate_text(text, target_language="en"):
    """
    Google Cloud Translation API를 비동기로 호출하여 텍스트를 영어로 번역합니다.
    """
    url = f"https://translation.googleapis.com/language/translate/v2?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "q": text,
        "target": target_language
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                translated_text = data["data"]["translations"][0]["translatedText"]
                return translated_text
            else:
                print("번역 API 오류:", response.status)
                return None

# 5. 전체 파이프라인 실행
async def main():
    # 예시 댓글
    comment = ("중국 지금 내수시장 개박살나서 수출로 어찌저찌 버티는중인데 "
               "미국이 관세 폭탄 던져서 수출길 막히면 중국에서 일자리 창출하고 수출하던 "
               "기업들 죄다 주변국으로 분산되면 결국 ㅈ되는건 중국인데 댓글들 왜이래?")
    
    # 1. 키워드 추출
    keywords = extract_keywords(comment)
    print("추출된 키워드:", keywords)

    # 2. 기사 크롤링
    article_text = """
    중국 내수시장이 위축되고 있는 가운데, 정부는 다양한 정책으로 수출 다각화를 시도하고 있다.
    여러 공식 매체와 경제 전문가는 미국의 관세 정책이 중국 경제에 미치는 영향을 면밀히 분석 중이다.
    또한, 일부 국제 뉴스에서는 중국 기업들이 해외 시장으로의 진출을 활발히 추진하고 있다는 보도가 이어지고 있다.
    """
    
    
    # 3. 기사에서 유사 문장 추출
    similar_sentences = extract_similar_sentences(article_text, comment, top_k=3)
    print("\n기사 내에서 추출된 유사 문장들:")
    for idx, sent in enumerate(similar_sentences, 1):
        print(f"{idx}. {sent}")
    
    # 4. 댓글과 유사 문장들의 영어 번역
    translation_tasks = []
    # 댓글 번역
    translation_tasks.append(translate_text(comment))
    # 추출된 각 문장 번역
    for sent in similar_sentences:
        translation_tasks.append(translate_text(sent))
    
    translations = await asyncio.gather(*translation_tasks)
    
    print("\n영어 번역 결과:")
    print("댓글 번역:", translations[0])
    for idx, trans in enumerate(translations[1:], 1):
        print(f"유사 문장 {idx} 번역:", trans)

# 전체 파이프라인 실행
if __name__ == "__main__":
    asyncio.run(main())
