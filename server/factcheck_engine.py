from services.data_models import CoreSentence, Claim
from services.api import extract_keywords, translate_text
from services.inference import (
    rank_keywords,
    find_top_k_answers_regex,
    analyze_claim_with_evidence,
)
from services.collector import collect_data
import math

from dataclasses import dataclass
from typing import List, Tuple, Dict
from tools.log_utils import logger


class CommentFactCheck:
    def __init__(
        self, comment: str, keywords: List[str], video_ctx: dict | None = None
    ):
        self.claim = Claim(comment)
        self.keywords = keywords
        self.video_ctx = video_ctx or {}
        self.best_article = None

    def analyze(self):
        print("[CommentFactCheck] Analyzing comment...\n", self.claim.text)
        # 1. 키워드 추출 → 기사 수집
        self.articles = self._get_related_articles()

        # 2. 주장 번역
        self.claim.text_en = translate_text(self.claim.text)

        # 3. 핵심 문장 추출 및 번역
        self._extract_core_sentences()

        # 4. NLI 수행
        self._nli_claim_with_core_sentences()

        # 5. 점수 계산 및 대표 기사 선택
        self.score = self._calculate_score()
        self.best_article = self._get_best_article()
        # logger.log_crawled_news("1", "http", self.articles)
        logger.log_claim_analysis(self.claim, self.articles[0][1])

    def _get_related_articles(self):
        articles = []
        ranked_keywords = rank_keywords(self.keywords, self.video_ctx)
        for k in range(len(ranked_keywords), 0, -1):
            keyword_subset = ranked_keywords[:k]  # 상위 k개만 유지
            print(f"\nkeyword_subset:{keyword_subset}\n")
            articles = collect_data(keyword_subset)
            if articles:
                break

        return articles

    def _extract_core_sentences(self):
        print("[CommentFactCheck] Extracting sentences and translating...")
        for article in self.articles:
            sentences = find_top_k_answers_regex(self.claim.text, article[2])
            for sentence, score in sentences:
                sentence_en = translate_text(sentence)
                core_sentence = CoreSentence(sentence, sentence_en, score)
                self.claim.core_sentences.append(core_sentence)

    def _nli_claim_with_core_sentences(self):
        for core_sentence in self.claim.core_sentences:
            res = analyze_claim_with_evidence(
                self.claim.text_en, core_sentence.sentence_en
            )
            core_sentence.nli_result["confidence"] = res["confidence"]
            core_sentence.nli_result["label"] = res["label"]
        return

    def _calculate_score(self):
        score = 0
        for core_sentence in self.claim.core_sentences:
            if core_sentence.nli_result["label"] == "entailment":
                score += (
                    core_sentence.nli_result["confidence"]
                    * core_sentence.similarity_score.item()
                )
            elif core_sentence.nli_result["label"] == "contradiction":
                score -= (
                    core_sentence.nli_result["confidence"]
                    * core_sentence.similarity_score.item()
                )
        score = self._sharpen_score_sigmoid(
            0.5 + score / (2 * len(self.claim.core_sentences))
            if self.claim.core_sentences
            else 0.5
        )
        return score

    def _sharpen_score_sigmoid(self, x, sharpness=10):
        return 1 / (1 + math.exp(-sharpness * (x - 0.5)))

    def _get_best_article(self):

        max_conf = -1
        arg_max = 0
        for i, core_sentence in enumerate(self.claim.core_sentences):
            result = core_sentence.nli_result
            if result["confidence"] > max_conf:
                max_conf = result["confidence"]
                arg_max = i
        article_index = arg_max // 3
        return self.articles[article_index] if self.articles else None

    def summary(self):
        return {
            "comment": self.claim,
            "score": self.score,
            "best_article": self.best_article,
        }
