from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict
from typing import TYPE_CHECKING

import networkx as nx

from api.parsers import oa_short_id
from core.config import POLITE_DELAY
from core.style import styled, truncate, Colour
from model.paper import Paper

if TYPE_CHECKING:
    from api.client import OpenAlexClient


def build_graph(
    seed_ids: list[str],
    *,
    depth: int = 1,
    max_nodes: int = 100,
    client: "OpenAlexClient",
) -> nx.DiGraph:
    from api.client import OpenAlexClient  # lazy to avoid circular
    graph = nx.DiGraph()
    visited = set()
    queue = deque((pid, 0) for pid in seed_ids)

    print(styled("\n  Building citation graph", Colour.BOLD))
    print(styled(
        f"  Seeds: {len(seed_ids)}  |  Depth: {depth}  |  Max nodes: {max_nodes}\n",
        Colour.DIM,
    ))

    while queue and len(graph) < max_nodes:
        paper_id, current_depth = queue.popleft()
        if paper_id in visited:
            continue
        visited.add(paper_id)

        _log_fetch(paper_id, len(graph), current_depth)
        raw = client.fetch_paper(paper_id)
        time.sleep(POLITE_DELAY)

        if not raw or not raw.get("id"):
            continue

        paper = Paper.from_api_response(raw, is_seed=(current_depth == 0))
        _add_paper_node(graph, paper)

        if current_depth >= depth:
            continue

        neighbour_ids = _add_edges_from_raw(graph, raw, paper.paper_id, client)
        for npid in neighbour_ids:
            if len(graph) < max_nodes and npid not in visited:
                queue.append((npid, current_depth + 1))

    _print_graph_summary(graph)
    return graph


def _add_paper_node(graph: nx.DiGraph, paper: Paper) -> None:
    graph.add_node(paper.paper_id, **{k: v for k, v in asdict(paper).items() if k != "paper_id"})


def _add_edges_from_raw(
    graph: nx.DiGraph,
    raw: dict,
    source_id: str,
    client: "OpenAlexClient",
):
    ref_uris = raw.get('referenced_works') or []
    if not ref_uris:
        return []

    ref_ids = [oa_short_id(uri) for uri in ref_uris if uri]
    unknown_ids = [rid for rid in ref_ids if rid not in graph]
    if unknown_ids:
        stubs = client.fetch_papers_by_ids(unknown_ids)
        time.sleep(POLITE_DELAY)
        for stub_raw in stubs:
            if stub_raw.get("id"):
                stub = Paper.stub_from_api(stub_raw)
                _ensure_stub_node(graph, stub.paper_id, stub_raw)

    neighbour_ids = []
    for rid in ref_ids:
        if rid not in graph:
            graph.add_node(
                rid,
                title="Unknown", year=None, authors=[], citation_count=0,
                abstract="", venue="", is_seed=False, doi="", arxiv="",
                pagerank=0.0, in_degree=0, out_degree=0,
            )
        graph.add_edge(source_id, rid, edge_type="references")
        neighbour_ids.append(rid)
    return neighbour_ids


def _ensure_stub_node(graph: nx.DiGraph, paper_id: str, raw: dict) -> None:
    if paper_id not in graph:
        stub = Paper.stub_from_api(raw)
        _add_paper_node(graph, stub)


def _log_fetch(paper_id, node_count, depth):
    print(
        f"  {styled('→', Colour.CYAN)} "
        f"[{node_count:>3}] "
        f"{styled(truncate(paper_id, 25), Colour.DIM)} "
        f"depth={depth}"
    )


def _print_graph_summary(graph):
    print(
        f"\n  {styled('✓', Colour.GREEN)} "
        f"Graph complete: "
        f"{styled(len(graph.nodes), Colour.BOLD)} nodes, "
        f"{styled(len(graph.edges), Colour.BOLD)} edges\n"
    )
