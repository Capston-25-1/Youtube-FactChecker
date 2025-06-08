from services.data_models import CoreSentence, Claim
from services.api import translate_text, translate_text_bulk
from services.inference import (
    rank_keywords,
    find_top_k_answers_regex,
    find_top_k_answers_regex_cache,
    analyze_claim_with_evidence,
)
from services.collector import collect_data, cache_articles
import math

from dataclasses import dataclass
from typing import List, Tuple, Dict
from tools.log_utils import logger
import time


class CommentFactCheck:
    def __init__(
        self,
        comment: str,
        keywords: List[str],
        video_ctx: dict | None = None,
        video_summary: str | None = None,
    ):
        self.claim = Claim(comment, keywords)
        self.video_ctx = video_ctx or {}
        self.video_summary = video_summary
        self.best_article = None
        self.articles = None
        self.best_sentence = None

    def analyze(self):
        print("[CommentFactCheck] Analyzing comment...\n", self.claim.text)
        # 전체 시작 시간
        start_total = time.time()

        # 1. 키워드 추출 → 기사 수집
        start = time.time()
        self.articles = self._get_related_articles()
        end = time.time()
        print(f"[1] 기사 수집 시간: {end - start:.3f}초")

        # 2. 주장 번역
        start = time.time()
        self.claim.text_en = translate_text(self.claim.text)
        end = time.time()
        print(f"[2] 주장 번역 시간: {end - start:.3f}초")

        # 3. 핵심 문장 추출 및 번역
        start = time.time()
        self._extract_core_sentences()
        end = time.time()
        print(f"[3] 핵심 문장 처리 시간: {end - start:.3f}초")

        # 4. NLI 수행
        start = time.time()
        self._nli_claim_with_core_sentences()
        end = time.time()
        print(f"[4] NLI 수행 시간: {end - start:.3f}초")

        # 5. 점수 계산 및 대표 기사 선택
        start = time.time()
        self.score = self._calculate_score()
        self.best_article = self._get_best_article()
        end = time.time()
        print(f"[5] 점수 계산 및 기사 선택 시간: {end - start:.3f}초")

        # 로그 저장
        articles = [article[1] for article in self.articles]
        logger.log_claim_analysis(self.claim, articles)

        # 전체 실행 시간
        end_total = time.time()
        print(f"[Total] 전체 분석 시간: {end_total - start_total:.3f}초")

    def _get_related_articles(self):
        articles = []
        ranked_keywords = rank_keywords(self.claim.keywords, self.video_ctx)
        for k in range(len(ranked_keywords), 0, -1):
            keyword_subset = ranked_keywords[:k]  # 상위 k개만 유지
            print(f"\nkeyword_subset:{keyword_subset}\n")
            articles = collect_data(keyword_subset)
            if articles:
                self.claim.keywords_used = keyword_subset
                break

        return articles

    def _extract_core_sentences(self):
        print("[CommentFactCheck] Extracting sentences and translating...")

        core_sentences = []

        # 1. 핵심 문장 추출
        for i, article in enumerate(self.articles):
            if article[3] is None:
                sentences, embeddings = find_top_k_answers_regex(
                    self.claim.text, article[2]
                )
                article[3] = embeddings.tolist()
            else:
                sentences = find_top_k_answers_regex_cache(
                    self.claim.text, article[2], article[3]
                )

            for sentence, score in sentences:
                core_sentences.append(sentence)
                core_sentence = CoreSentence(sentence, "", score)
                core_sentence.article_idx = i
                self.claim.core_sentences.append(core_sentence)

        # 2. 문장 번역
        sentences_en = translate_text_bulk(core_sentences)

        # 3. 번역 결과 저장
        for i, core_sentence in enumerate(self.claim.core_sentences):
            core_sentence.sentence_en = sentences_en[i]

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
        has_result = False
        for core_sentence in self.claim.core_sentences:
            if core_sentence.nli_result["label"] == "entailment":
                score += (
                    core_sentence.nli_result["confidence"]
                    * core_sentence.similarity_score.item()
                )
                has_result = True
            elif core_sentence.nli_result["label"] == "contradiction":
                score -= (
                    core_sentence.nli_result["confidence"]
                    * core_sentence.similarity_score.item()
                )
                has_result = True
        if not has_result:
            return -1
        score = self._sharpen_score_sigmoid(
            0.5 + score / (2 * len(self.claim.core_sentences))
            if self.claim.core_sentences
            else -1
        )
        return score

    def _sharpen_score_sigmoid(self, x, sharpness=15):
        return 1 / (1 + math.exp(-sharpness * (x - 0.5)))

    def _get_best_article(self):

        max_conf = -1
        arg_max = 0
        for core_sentence in self.claim.core_sentences:
            result = core_sentence.nli_result
            if result["label"] != "neutral" and result["confidence"] > max_conf:
                max_conf = result["confidence"]
                arg_max = core_sentence.article_idx
                self.best_sentence = core_sentence.sentence
        article_index = arg_max
        return self.articles[article_index] if self.articles else self.articles[0]

    def cache_result(self):
        cache_articles(self.claim.keywords, self.articles)

    def summary(self):
        return {
            "comment": self.claim,
            "score": self.score,
            "best_article": self.best_article,
        }
