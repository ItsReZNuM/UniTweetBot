
import re

_ARABIC_TO_PERSIAN = str.maketrans({
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "ؤ": "و",
    "إ": "ا",
    "أ": "ا",
    "ٱ": "ا",
})

def normalize_fa(text: str) -> str:
    if not text:
        return ""

    t = text.strip()
    t = t.translate(_ARABIC_TO_PERSIAN)

    t = t.replace("\u200c", " ")  
    t = t.replace("\u200f", "")
    t = t.replace("\u202a", "").replace("\u202b", "").replace("\u202c", "")

    t = re.sub(r"[ـ_•،؛,:!؟\-\(\)\[\]\{\}<>\"'`~@#$%^&*+=|\\/]", " ", t)

    t = re.sub(r"\s+", " ", t).strip()

    return t
