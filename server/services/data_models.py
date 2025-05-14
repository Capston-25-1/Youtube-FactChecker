class CoreSentence:
    def __init__(self, sentence, sentence_en, score):
        self.sentence = sentence
        self.sentence_en = sentence_en
        self.article_idx = None
        self.sentence_index = None
        self.similarity_score = score
        self.nli_result = {"confidence": None, "label": None}

    def to_dict(self):
        return {"sentence": self.sentence, "score": self.similarity_score.item()}


class Claim:
    def __init__(self, text, keywords):
        self.text = text
        self.text_en = None
        self.keywords = keywords
        self.core_sentences = []

    def to_dict(self):
        return {"text": self.text, "text_en": self.text_en, "keywords": self.keywords}
