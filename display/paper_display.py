from __future__ import annotations

import sys
from typing import Optional

import networkx as nx

from core.style import styled, truncate, Colour


def print_paper(
    node_id: str,
    attrs: dict,
    *,
    rank: Optional[int] = None,
    show_abstract: bool = False,
) -> None:
    prefix = f"  {styled(f'#{rank}', Colour.DIM)} " if rank else "  "
    seed_tag = styled(" [SEED]", Colour.YELLOW) if attrs.get("is_seed") else ""
    year_str = styled(f" {attrs.get('year', '?')}", Colour.BLUE)
    title_str = styled(truncate(attrs.get("title", "?"), 68), Colour.WHITE, Colour.BOLD)
    print(f"{prefix}{title_str}{seed_tag}{year_str}")

    meta_parts = _paper_meta_parts(attrs)
    print(f"  {'  '.join(meta_parts)}")

    if show_abstract and attrs.get("abstract"):
        _print_wrapped(attrs["abstract"], indent=2, width=68)

    links = _paper_links(node_id, attrs)
    print(f"  {styled(' | '.join(links), Colour.DIM)}")


def _paper_meta_parts(attrs):
    parts = []
    authors = attrs.get("authors", [])
    if authors:
        line = ", ".join(authors[:3])
        if len(authors) > 3:
            line += " et al."
        parts.append(styled(line, Colour.DIM))
    if attrs.get("venue"):
        parts.append(styled(attrs["venue"], Colour.DIM))
    parts.append(styled(f"{attrs.get('citation_count', 0)} citations", Colour.CYAN))
    if attrs.get("pagerank"):
        parts.append(styled(f"PR={attrs['pagerank']:.5f}", Colour.MAGENTA))
    return parts


def _paper_links(node_id: str, attrs: dict) -> list[str]:
    links: list[str] = []
    if attrs.get("doi"):
        links.append(f"DOI: https://doi.org/{attrs['doi']}")
    if attrs.get("arxiv"):
        links.append(f"arXiv: https://arxiv.org/abs/{attrs['arxiv']}")
    links.append(f"Link: https://openalex.org/{node_id}")
    return links


def _print_wrapped(text, *, indent, width):
    pad = " " * indent
    words = text.split()
    line = []
    for word in words:
        if sum(len(w) + 1 for w in line) + len(word) > width:
            print(f"{pad}{styled(' '.join(line), Colour.DIM)}")
            line = [word]
        else:
            line.append(word)
    if line:
        print(f"{pad}{styled(' '.join(line), Colour.DIM)}")


def resolve_paper_id(graph: nx.DiGraph, query: str) -> Optional[str]:
    if query in graph:
        return query
    matches = [
        (nid, d)
        for nid, d in graph.nodes(data=True)
        if query.lower() in (d.get("title") or "").lower()
    ]
    if not matches:
        print(styled(f"\n  Paper not found: {query}\n", Colour.RED), file=sys.stderr)
        print(styled("  try litgraph top <file> to see ids\n", Colour.DIM), file=sys.stderr)
        return None
    if len(matches) == 1:
        return matches[0][0]
    print(styled(f'\n  Multiple matches for "{query}":\n', Colour.YELLOW))
    for nid, data in matches[:10]:
        print(f"  {styled(nid[:20], Colour.DIM)}  {truncate(data.get('title', '?'), 60)}")
    print()
    return None


def print_neighbour_list(
    graph: nx.DiGraph,
    neighbour_ids: list[str],
    *,
    label: str,
    limit: int = 8,
) -> None:
    if not neighbour_ids:
        return
    print(f"\n  {styled(f'{label} ({len(neighbour_ids)} in graph):', Colour.BOLD)}")
    for npid in neighbour_ids[:limit]:
        nd = graph.nodes.get(npid, {})
        print(
            f"  {styled('·', Colour.DIM)} "
            f"{truncate(nd.get('title', '?'), 62)} "
            f"{styled(nd.get('year', '?'), Colour.BLUE)}"
        )
    if len(neighbour_ids) > limit:
        print(styled(f"  … and {len(neighbour_ids) - limit} more", Colour.DIM))
