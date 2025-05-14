from .api import scrape_article
import os
import pickle
import hashlib
from typing import List, Tuple

CACHE_DIR = "cache"


def collect_data(query):
    return scrape_article(query)


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
