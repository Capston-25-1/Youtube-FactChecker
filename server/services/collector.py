import os
import pickle
import hashlib
import requests
from typing import List, Tuple
from newspaper import Article
from urllib.parse import urlencode
from bs4 import BeautifulSoup

CACHE_DIR = "cache"


def collect_data(keyword: list[str], pages: int = 1):
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
                # newspaper3k 사용하여 기사 본문 추출
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


def get_cache_filename(keyword: List[str], pages: int) -> str:
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    # 캐시 키 생성 (해시로 중복 방지)
    key_str = "_".join(keyword) + f"_p{pages}"
    hashed = hashlib.md5(key_str.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{hashed}.pkl")


def get_articles_with_cache(
    keyword: List[str], pages: int = 1
) -> List[Tuple[str, str, str]]:
    cache_file = get_cache_filename(keyword, pages)

    # 캐시가 있다면 로드
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            print(f"캐시에서 로드: {keyword}")
            return pickle.load(f)

    # 없으면 크롤링 후 저장
    print(f"새로 크롤링: {keyword}")
    result = scrape_article(keyword, pages)

    with open(cache_file, "wb") as f:
        pickle.dump(result, f)

    return result
