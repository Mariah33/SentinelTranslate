def postprocess_line(t: str) -> str:
    t = t.replace("▁", " ").strip()
    t = " ".join(t.split())
    return t


def postprocess(lines):
    return " ".join([postprocess_line(x) for x in lines])
