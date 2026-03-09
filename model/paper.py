from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from api.parsers import (
    oa_abstract,
    oa_arxiv,
    oa_authors,
    oa_doi,
    oa_short_id,
    oa_venue,
)
from core.config import ABSTRACT_LIMIT


@dataclass
class Paper:
    paper_id: str
    title: str = "Unknown"
    year: Optional[int] = None
    authors: list[str] = field(default_factory=list)
    citation_count: int = 0
    abstract: str = ""
    venue: str = ""
    is_seed: bool = False
    doi: str = ""
    arxiv: str = ""

    pagerank: float = 0.0
    in_degree: int = 0
    out_degree: int = 0

    @classmethod
    def from_api_response(cls, raw: dict, *, is_seed: bool = False) -> "Paper":
        return cls(
            paper_id=oa_short_id(raw.get("id") or ""),
            title=raw.get("title") or "Unknown",
            year=raw.get("publication_year"),
            authors=oa_authors(raw),
            citation_count=raw.get("cited_by_count") or 0,
            abstract=oa_abstract(raw)[:ABSTRACT_LIMIT],
            venue=oa_venue(raw),
            is_seed=is_seed,
            doi=oa_doi(raw),
            arxiv=oa_arxiv(raw),
        )

    @classmethod
    def stub_from_api(cls, raw: dict) -> "Paper":
        return cls(
            paper_id=oa_short_id(raw.get("id") or ""),
            title=raw.get("title") or "Unknown",
            year=raw.get("publication_year"),
            authors=oa_authors(raw),
            citation_count=raw.get("cited_by_count") or 0,
            venue=oa_venue(raw),
        )
