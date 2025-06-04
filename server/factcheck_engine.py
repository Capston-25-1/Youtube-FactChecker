from services.data_models import CoreSentence, Claim
from services.api import translate_text, translate_text_bulk
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
import time


class CommentFactCheck:
    def __init__(
        self, comment: str, keywords: List[str], video_ctx: dict | None = None
    ):
        self.claim = Claim(comment, keywords)
        self.video_ctx = video_ctx or {}
        self.best_article = None

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
                break

        return articles

    def _extract_core_sentences(self):
        print("[CommentFactCheck] Extracting sentences and translating...")

        core_sentences = []

        # 1. 핵심 문장 추출
        total_extract_start = time.time()
        for article in self.articles:
            start_extract = time.time()
            sentences = find_top_k_answers_regex(self.claim.text, article[2])
            end_extract = time.time()
            print(
                f"[문장 추출] {len(sentences)}개 문장 추출 완료: {end_extract - start_extract:.3f}초"
            )

            for sentence, score in sentences:
                core_sentences.append(sentence)
                core_sentence = CoreSentence(sentence, "", score)
                self.claim.core_sentences.append(core_sentence)
        total_extract_end = time.time()
        print(f"[총 추출 시간] {total_extract_end - total_extract_start:.3f}초")

        # 2. 문장 번역
        start_translate = time.time()
        sentences_en = translate_text_bulk(core_sentences)
        end_translate = time.time()
        print(
            f"[번역] 총 {len(sentences_en)}개 문장 번역 완료: {end_translate - start_translate:.3f}초"
        )

        # 3. 번역 결과 저장
        start_store = time.time()
        for i, core_sentence in enumerate(self.claim.core_sentences):
            core_sentence.sentence_en = sentences_en[i]
        end_store = time.time()
        print(f"[저장] 번역 결과 저장 완료: {end_store - start_store:.3f}초")

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
