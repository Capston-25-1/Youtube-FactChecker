from services.data_models import CoreSentence, Claim
from services.api import extract_keywords, translate_text
from services.inference import (
    find_top_k_answers_regex,
    analyze_claim_with_evidences,
)
from services.collector import collect_data
from tools.log_utils import logger


class CommentFactCheck:
    def __init__(self, comment: str):
        self.comment = comment
        self.claims = []

        self.core_sentences = []
        self.core_sentences_en = []
        self.best_article = None

    def analyze(self):
        print("[CommentFactCheck] Analyzing comment...\n", self.comment)
        # 1. 키워드 추출 → 기사 수집
        self.articles = self._get_related_articles()

        # 2. 주장 번역
        for claim in self.claims:
            claim.text_en = translate_text(claim.text)

        # 3. 핵심 문장 추출 및 번역
        self._extract_core_sentences()

        # 4. NLI 수행
        self.nli_results = analyze_claim_with_evidences(
            self.claims[0].text, self.core_sentences_en
        )

        # 5. 점수 계산 및 대표 기사 선택
        self.score = self._calculate_score()
        self.best_article = self._get_best_article()
        # logger.log_crawled_news("1", "http", self.articles)
        logger.log_comment_analysis(
            self.comment, self.claims[0], self.articles[0][1], self.core_sentences
        )

    def _get_related_articles(self):
        num_keywords = 6
        articles = []

        while not articles and num_keywords > 0:
            claims_info = extract_keywords(self.comment, num_keywords)
            print("[factchecker.py]: extracted claims_info\n", claims_info)

            keyword_list = []
            for entry in claims_info:
                # entry는 {"claim": str, "keywords": [str,...]}
                claim = Claim(entry["claim"], entry["keywords"])
                keyword_list.extend(entry.get("keywords", []))
                self.claims.append(claim)
            print("[factchecker.py]: using keyword_list\n", keyword_list)

            # 3) 평탄화된 키워드 리스트로 기사 스크래핑 시도
            articles = collect_data(keyword_list)
            num_keywords -= 1

        return articles

    def _extract_core_sentences(self):
        print("[CommentFactCheck] Extracting sentences and translating...")
        for article in self.articles:
            sentences = find_top_k_answers_regex(self.comment, article[2])
            for sentence, _ in sentences:
                sentence_en = translate_text(sentence)
                self.core_sentences.append(sentence)
                self.core_sentences_en.append(sentence_en)

    def _calculate_score(self):
        score = 0
        for result in self.nli_results:
            if result["label"] == "entailment":
                score += result["confidence"]
            elif result["label"] == "contradiction":
                score -= result["confidence"]
        return 0.5 + score / (2 * len(self.nli_results)) if self.nli_results else 0.5

    def _get_best_article(self):
        if not self.nli_results:
            return None
        max_conf = -1
        arg_max = 0
        for i, result in enumerate(self.nli_results):
            if result["confidence"] > max_conf:
                max_conf = result["confidence"]
                arg_max = i
        article_index = arg_max // 3
        return self.articles[article_index] if self.articles else None

    def summary(self):
        return {
            "comment": self.comment,
            "score": self.score,
            "best_article": self.best_article,
            "core_sentences": self.core_sentences,
            "nli_results": self.nli_results,
        }
