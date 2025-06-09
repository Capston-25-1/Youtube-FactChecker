import os
import json
import hashlib
from typing import List, Tuple
from services.api import crawl_article
from random import sample

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(base_dir, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def collect_data(keyword: list[str], pages: int = 1):
    cache_candidate = get_best_cache_candidate(keyword)

    if cache_candidate and cache_candidate["similarity"] >= 1.0:
        print("[collector.py]: 캐시 100% 활용 - 크롤링 생략")
        return cache_candidate["articles"]
    new_articles = crawl_article(keyword, pages)  # [(title, url, body, embedding), ...]

    if cache_candidate is None:
        # 캐시 없으면 새로 수집한 기사 전부 반환
        return new_articles

    # 유사도가 가장 높은 캐시 기사만 사용
    cached_articles = cache_candidate["articles"]
    sim = cache_candidate["similarity"]

    total_needed = len(new_articles)
    use_count = int(sim * total_needed)

    # 캐시 기사에서 일부 사용
    result_articles = []
    if use_count > 0:
        result_articles.extend(
            sample(cached_articles, min(use_count, len(cached_articles)))
        )
    # 나머지는 새로 수집한 기사로 채움
    remaining_count = max(0, total_needed - len(result_articles))
    result_articles.extend(new_articles[:remaining_count])
    print(
        f"[collector.py]: total:{total_needed}, cache:{use_count}, new:{remaining_count}"
    )

    # 중복 제거 (url 기준)
    seen_urls = set()
    final_articles = []
    for article in result_articles:
        _, url, _, _ = article
        if url not in seen_urls:
            seen_urls.add(url)
            final_articles.append(article)

    return final_articles


def get_best_cache_candidate(keyword: list[str]):
    best_filename = None
    best_sim = 0

    for filename in os.listdir(CACHE_DIR):
        if not filename.endswith(".json"):
            continue

        file2keyword = filename[:-5].split("_")  # '.json' 빼고 키워드 리스트 추출
        sim = keyword_similarity(file2keyword, keyword)

        if sim > best_sim and sim >= 0.3:
            best_sim = sim
            best_filename = filename

    if best_filename is None:
        return None

    # 가장 유사한 파일 하나만 열기
    try:
        path = os.path.join(CACHE_DIR, best_filename)
        with open(path, "r", encoding="utf-8") as f:
            articles = json.load(f)
        return {
            "similarity": best_sim,
            "articles": articles,
        }
    except Exception as e:
        print(f"[CacheError] {best_filename}: {e}")
        return None


def keyword_similarity(keyword1, keyword2):
    return len(set(keyword1) & set(keyword2)) / min(len(keyword1), len(keyword2))


def cache_articles(keyword: list[str], articles: list[tuple]):
    """
    articles: List of tuples (title, url, body, embedding)
    """
    filename = os.path.join(CACHE_DIR, "_".join(keyword) + ".json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False)
