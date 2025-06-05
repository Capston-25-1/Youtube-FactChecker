import re
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline

# 모델 로드 (CPU 실행)
embedding_model = SentenceTransformer(
    "snunlp/KR-SBERT-V40K-klueNLI-augSTS", device="cpu"
)
# NLI 파이프라인 생성
nli_pipeline = pipeline(
    "text-classification", model="roberta-large-mnli", truncation=True, max_length=512
)


def rank_keywords(keywords, video_ctx):
    video_corpus = ". ".join(
        [
            video_ctx.get("title", "").strip(". "),
            video_ctx.get("description", "").strip(". "),
            " ".join(video_ctx.get("hashtags", [])),
        ]
    )
    video_emb = embedding_model.encode(video_corpus, convert_to_tensor=True)

    ranked = []
    for kw in keywords:
        kw_emb = embedding_model.encode(kw, convert_to_tensor=True)
        score = util.cos_sim(kw_emb, video_emb).item()
        ranked.append((kw, score))

    ranked.sort(key=lambda x: x[1], reverse=True)  # 중요도 높은 순
    return [kw for kw, _ in ranked]


def find_top_k_answers_regex(query, sentences, k=3):
    """
    Finds the top k sentences from a given text that are most similar to a query using cosine similarity of sentence embeddings.

    Args:
        text (str): The text from which to extract sentences.
        query (str): The query sentence to compare against.
        k (int, optional): The number of top similar sentences to return. Defaults to 3.

    Returns:
        list[tuple]: A list of tuples, each containing a sentence and its similarity score, ordered by similarity in descending order.
    """

    # 문장 임베딩 생성
    sentence_embeddings = embedding_model.encode(sentences)

    # 질문 임베딩 생성
    query_embedding = embedding_model.encode(query)

    # 질문과 각 문장 간의 유사도 계산
    similarities = util.cos_sim(query_embedding, sentence_embeddings)[0]

    # 유사도와 문장 인덱스를 함께 저장
    sentence_scores = list(zip(sentences, similarities))

    # 유사도 0.5 이상 필터링
    filtered_sentence_scores = [s for s in sentence_scores if s[1] >= 0.5]

    # 유사도 기준으로 내림차순 정렬
    filtered_sentence_scores = sorted(
        filtered_sentence_scores, key=lambda x: x[1], reverse=True
    )

    # 상위 k개 문장 반환
    top_k_sentences_with_scores = filtered_sentence_scores[:k]
    top_k_scores = []
    for sentence_score in top_k_sentences_with_scores:
        top_k_scores.append(sentence_score[1])
    print("[inference.py]:", top_k_sentences_with_scores)

    return top_k_sentences_with_scores, sentence_embeddings


def find_top_k_answers_regex_cache(query, sentences, sentence_embeddings, k=3):
    # 질문 임베딩 생성
    query_embedding = embedding_model.encode(query)

    # 질문과 각 문장 간의 유사도 계산
    similarities = util.cos_sim(query_embedding, sentence_embeddings)[0]

    # 유사도와 문장 인덱스를 함께 저장
    sentence_scores = list(zip(sentences, similarities))

    # 유사도 0.5 이상 필터링
    filtered_sentence_scores = [s for s in sentence_scores if s[1] >= 0.5]

    # 유사도 기준으로 내림차순 정렬
    filtered_sentence_scores = sorted(
        filtered_sentence_scores, key=lambda x: x[1], reverse=True
    )

    # 상위 k개 문장 반환
    top_k_sentences_with_scores = filtered_sentence_scores[:k]
    top_k_scores = []
    for sentence_score in top_k_sentences_with_scores:
        top_k_scores.append(sentence_score[1])
    print("[inference.py]:", top_k_sentences_with_scores)

    return top_k_sentences_with_scores


def analyze_claim_with_evidences(claim, evidences):
    """
    각 evidence가 claim에 대해 어떤 판단(entailment, contradiction, neutral)을 하는지 분석합니다.

    Args:
        claim (str): 확인하고자 하는 주장
        evidences (list[str]): 해당 주장과 비교할 증거 문장들

    Returns:
        list[dict]: 각 evidence에 대한 판단 결과 리스트
    """
    results = []

    for evidence in evidences:
        # NLI 모델 입력: premise = evidence, hypothesis = claim
        output = nli_pipeline(f"{evidence} [SEP] {claim}")

        # 결과는 label과 score가 포함된 리스트 (보통 첫 번째가 가장 높은 점수)
        label = output[0]["label"]
        score = output[0]["score"]
        results.append(
            {
                "evidence": evidence,
                "label": label.lower(),  # entailment, contradiction, neutral
                "confidence": round(score, 4),
            }
        )

    return results


def analyze_claim_with_evidence(claim, evidence):
    """
    각 evidence가 claim에 대해 어떤 판단(entailment, contradiction, neutral)을 하는지 분석합니다.

    Args:
        claim (str): 확인하고자 하는 주장
        evidences (list[str]): 해당 주장과 비교할 증거 문장들

    Returns:
        list[dict]: 각 evidence에 대한 판단 결과 리스트
    """

    # NLI 모델 입력: premise = evidence, hypothesis = claim
    output = nli_pipeline(f"{evidence} [SEP] {claim}")

    # 결과는 label과 score가 포함된 리스트 (보통 첫 번째가 가장 높은 점수)
    label = output[0]["label"]
    score = output[0]["score"]

    return {"label": label.lower(), "confidence": round(score, 4)}
