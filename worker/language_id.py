import langid


def detect_language(text: str) -> str:
    lang, _ = langid.classify(text)
    return lang


def validate_language(text: str, expected_lang: str) -> bool:
    detected = detect_language(text)
    return detected == expected_lang
