import re


def extract_numbers(text: str):
    return re.findall(r"\d+(?:[\.,]\d+)?", text)


def number_consistency(src: str, tgt: str) -> bool:
    src_nums = extract_numbers(src)
    tgt_nums = extract_numbers(tgt)

    if src_nums:
        for n in src_nums:
            if n not in tgt_nums:
                return False

    for n in tgt_nums:
        if n not in src_nums:
            return False

    return True
