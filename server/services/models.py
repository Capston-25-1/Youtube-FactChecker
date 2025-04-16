import re
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline

# 모델 로드 (CPU 실행)
embedding_model = SentenceTransformer(
    "snunlp/KR-SBERT-V40K-klueNLI-augSTS", device="cpu"
)
# NLI 파이프라인 생성
nli_pipeline = pipeline("text-classification", model="roberta-large-mnli")


def find_top_k_answers_regex(query, text, k=3):
    """
    Finds the top k sentences from a given text that are most similar to a query using cosine similarity of sentence embeddings.

    Args:
        text (str): The text from which to extract sentences.
        query (str): The query sentence to compare against.
        k (int, optional): The number of top similar sentences to return. Defaults to 3.

    Returns:
        list[tuple]: A list of tuples, each containing a sentence and its similarity score, ordered by similarity in descending order.
    """

    # 문장 분리 (마침표, 물음표, 느낌표 기준으로 분리)
    sentences = re.split(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s", text)

    # 문장 임베딩 생성
    sentence_embeddings = embedding_model.encode(sentences)

    # 질문 임베딩 생성
    query_embedding = embedding_model.encode(query)

    # 질문과 각 문장 간의 유사도 계산
    similarities = util.cos_sim(query_embedding, sentence_embeddings)[0]

    # 유사도와 문장 인덱스를 함께 저장
    sentence_scores = list(zip(sentences, similarities))

    # 유사도 기준으로 내림차순 정렬
    sentence_scores = sorted(sentence_scores, key=lambda x: x[1], reverse=True)

    # 상위 k개 문장 반환
    top_k_sentences_with_scores = sentence_scores[:k]
    top_k_scores = []
    for sentence_score in top_k_sentences_with_scores:
        top_k_scores.append(sentence_score[1])
    print("[modles.py]:", top_k_sentences_with_scores)
    print(
        "[modles.py]: found",
        len(top_k_sentences_with_scores),
        "sentences with",
        top_k_scores,
    )

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
