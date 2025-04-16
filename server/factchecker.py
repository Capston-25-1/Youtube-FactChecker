from services.api import extract_keywords, translate_text
from services.models import find_top_k_answers_regex, analyze_claim_with_evidences
from services.collecter import collect_data


def analyze_comment(comment):
    print("[factchecker.py]: analyzing comment\n", comment)
    keyword = extract_keywords(comment)
    print("[factchecker.py]: extracted keyword\n", keyword)
    articles = collect_data(keyword)

    core_sentences = []
    core_sentences_en = []

    print("[factchecker.py]: searching realted sentences and translating")
    for article in articles:
        sentences = find_top_k_answers_regex(comment, article)
        for sentence, _ in sentences:
            sentence_en = translate_text(sentence)
            core_sentences.append(sentence)
            core_sentences_en.append(sentence_en)

    comment_en = translate_text(comment)
    print(comment_en, core_sentences_en)
    results = analyze_claim_with_evidences(comment_en, core_sentences_en)
    for i in range(len(results)):
        print(
            "[factchecker.py] NLI task result:",
            results[i]["evidence"],
            results[i]["label"],
            results[i]["confidence"],
        )

    score = 0
    for res in results:
        if res["label"] == "entailment":
            score += 1
        elif res["label"] == "neutral":
            score += 0.5
    score = score / len(core_sentences)

    return score
