from collections import Counter
from typing import Any

from worker.language_id import validate_language
from worker.nercheck import ner_consistency
from worker.numcheck import number_consistency


def repetition_score(tokens: list[str], n: int = 3) -> int:
    ngrams: list[tuple[Any, ...]] = [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
    return max(Counter(ngrams).values()) if ngrams else 0


def length_ratio(src_tokens: list[str], tgt_tokens: list[str]) -> float:
    return len(tgt_tokens) / max(1, len(src_tokens))


def base_hallucination(src: str, tgt: str) -> bool:
    src_tokens = src.split()
    tgt_tokens = tgt.split()
    if length_ratio(src_tokens, tgt_tokens) > 2.5:
        return True
    if repetition_score(tgt_tokens, 3) > 2:
        return True
    return False


def detect_hallucination(src: str, tgt: str, src_lang: str) -> bool:
    if base_hallucination(src, tgt):
        return True
    if not validate_language(src, src_lang):
        return True
    if not number_consistency(src, tgt):
        return True
    if not ner_consistency(src, tgt):
        return True
    return False
