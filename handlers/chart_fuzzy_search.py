
from rapidfuzz import fuzz
from handlers.chart_normalizer import normalize_fa


def fuzzy_match(query: str, choices: list[dict], min_score: int = 85, limit: int = 10):

    q = normalize_fa(query)

    results = []
    for ch in choices:
        score = fuzz.token_set_ratio(q, ch["normalized_name"])
        if score >= min_score:
            results.append({
                "id": ch["id"],
                "major_name": ch["major_name"],
                "score": score
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
