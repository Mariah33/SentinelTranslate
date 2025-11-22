import spacy

nlp = spacy.load("en_core_web_sm")


def extract_ents(text: str):
    doc = nlp(text)
    return {ent.text for ent in doc.ents}


def ner_consistency(src: str, tgt: str) -> bool:
    ents_src = extract_ents(src)
    ents_tgt = extract_ents(tgt)

    if ents_src and not ents_tgt:
        return False

    if ents_tgt - ents_src:
        return False

    return True
