import os
import json
import hashlib
from typing import List, Tuple
from services.api import crawl_article
from data_models import Article

CACHE_DIR = "cache"


def collect_data(keyword: list[str], pages: int = 1):
    cache_articles = get_cache(keyword)
    new_article = crawl_article(keyword, pages)
    return new_article


def keyword_similarity(keyword1, keyword2):
    return len(set(keyword1) & set(keyword2))


def get_cache_filename(keyword: List[str], pages: int) -> str:
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    # 캐시 키 생성 (해시로 중복 방지)
    key_str = "_".join(keyword) + f"_p{pages}"
    hashed = hashlib.md5(key_str.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{hashed}.pkl")


def get_similar_keywords(keyword):
    pass


def get_cache(keyword):
    articles = []
    for file in os.listdir(CACHE_DIR):
        if keyword_similarity(file, keyword) > 0.8:
            with open(os.path.join(CACHE_DIR, file), "rb") as f:
                articles.append(json.loads(f.read()))

    if articles:
        return articles
    return None
