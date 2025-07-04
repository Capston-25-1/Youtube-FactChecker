class CoreSentence:
    def __init__(self, sentence, sentence_en, score):
        self.sentence = sentence
        self.sentence_en = sentence_en
        self.article_idx = None
        self.sentence_index = None
        self.similarity_score = score
        self.nli_result = {"confidence": None, "label": None}

    def to_dict(self):
        return {
            "sentence": self.sentence,
            "score": self.similarity_score.item(),
            "nli_result": self.nli_result,
            "article_idx": self.article_idx,
        }


class Claim:
    def __init__(self, text, keywords):
        self.text = text
        self.text_en = None
        self.keywords = keywords
        self.keywords_used = keywords
        self.core_sentences = []

    def to_dict(self):
        core_sentences = []
        for core_sentence in self.core_sentences:
            core_sentences.append(core_sentence.to_dict())
        return {
            "text": self.text,
            "text_en": self.text_en,
            "keywords": self.keywords,
            "keywords_used": self.keywords_used,
            "core_sentences": core_sentences,
        }
