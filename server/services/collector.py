import os
import pickle
import hashlib
from typing import List, Tuple
from services.api import crawl_article

CACHE_DIR = "cache"


def collect_data(keyword: list[str], pages: int = 1):

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
    result = craw(keyword, pages)

    with open(cache_file, "wb") as f:
        pickle.dump(result, f)

    return result
