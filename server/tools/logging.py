import os
import json
from datetime import datetime
from typing import List, Dict, Tuple


class NewsLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        self.crawl_log_path = os.path.join(log_dir, "news_crawled.jsonl")
        self.translation_log_path = os.path.join(log_dir, "news_translated.jsonl")
        self.comment_log_path = os.path.join(log_dir, "comment_analysis.jsonl")

    def _append_jsonl(self, filepath: str, data: Dict):
        data["timestamp"] = datetime.now().isoformat()
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def log_crawled_news(self, title: str, url: str, body: str):
        """1. 크롤링한 뉴스 기사 로깅"""
        log_data = {"title": title, "url": url, "body": body}
        self._append_jsonl(self.crawl_log_path, log_data)

    def log_translated_news(self, title: str, original: str, translated: str):
        """2. 번역된 뉴스 기사 로깅"""
        log_data = {
            "title": title,
            "original_text": original,
            "translated_text": translated,
        }
        self._append_jsonl(self.translation_log_path, log_data)

    def log_comment_analysis(
        self,
        comment: str,
        articles: List[Dict[str, str]],
        extracted_sentences: Dict[str, List[str]],
    ):
        """
        3. 댓글 기반 뉴스 정보 및 문장 로깅

        - comment: 원 댓글 텍스트
        - articles: [{title, url}]
        - extracted_sentences: {title: [sentence1, sentence2, ...]}
        """
        log_data = {
            "comment": comment,
            "related_articles": articles,
            "extracted_sentences": extracted_sentences,
        }
        self._append_jsonl(self.comment_log_path, log_data)
