import re

import nltk

nltk.download("punkt", quiet=True)


def normalize(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    return text


def sentence_split(text: str):
    return nltk.sent_tokenize(text)


def preprocess(text: str):
    text = normalize(text)
    return sentence_split(text)
