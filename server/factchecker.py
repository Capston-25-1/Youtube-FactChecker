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
        sentences = find_top_k_answers_regex(comment, article[2])
        for sentence, _ in sentences:
            sentence_en = translate_text(sentence)
            core_sentences.append(sentence)
            core_sentences_en.append(sentence_en)

    comment_en = translate_text(comment)
    print(comment_en, core_sentences_en)
    nli_results = analyze_claim_with_evidences(comment_en, core_sentences_en)
    for i in range(len(nli_results)):
        print(
            "[factchecker.py] NLI task result:",
            nli_results[i]["evidence"],
            nli_results[i]["label"],
            nli_results[i]["confidence"],
        )

    score = calculate_score(nli_results)
    max_index = get_max_confidence_article(nli_results)
    return score, articles[max_index]

def calculate_score(nli_results):
    score = 0
    for index in range(len(nli_results)):
        if nli_results[index]["label"] == "entailment":
            score += nli_results[index]["confidence"]
        elif nli_results[index]["label"] == "contradiction":
            score -= nli_results[index]["confidence"]
    score = 0.5 + score/(2*len(nli_results)) 
    
    return score

def get_max_confidence_article(nli_results):
    arg_max = 0
    max = 0
    for index in range(len(nli_results)):
        if nli_results[index]["confidence"] > max:
            max = nli_results[index]["confidence"]
            arg_max = index
    return arg_max//3