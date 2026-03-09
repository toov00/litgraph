from core.config import OA_ID_PREFIX


def oa_short_id(full_id: str) -> str:
    return full_id.removeprefix(OA_ID_PREFIX)


def oa_authors(raw: dict) -> list[str]:
    return [
        a.get("author", {}).get("display_name") or "Unknown"
        for a in (raw.get("authorships") or [])[:5]
    ]


def oa_venue(raw: dict) -> str:
    loc = raw.get("primary_location") or {}
    source = loc.get("source") or {}
    return source.get("display_name") or ""


def oa_doi(raw: dict) -> str:
    doi = (raw.get("ids") or {}).get("doi") or ""
    return doi.removeprefix("https://doi.org/")


def oa_arxiv(raw: dict) -> str:
    arxiv = (raw.get("ids") or {}).get("arxiv") or ""
    return arxiv.removeprefix("https://arxiv.org/abs/")


def oa_abstract(raw: dict) -> str:
    # they give us word->positions, gotta put it back in order
    inv = raw.get("abstract_inverted_index")
    if not inv:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inv.items():
        for idx in idxs:
            positions[idx] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions))
