#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import networkx as nx
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

_API_BASE = "https://api.openalex.org"

_FULL_SELECT = (
    "id,title,publication_year,authorships,cited_by_count,"
    "abstract_inverted_index,primary_location,ids,"
    "referenced_works,related_works"
)
_STUB_SELECT = (
    "id,title,publication_year,authorships,cited_by_count,primary_location"
)

_REQUEST_TIMEOUT = 20         
_POLITE_DELAY    = 0.1         
_RATE_LIMIT_WAIT = 10          
_MAX_RETRIES     = 3         
_ABSTRACT_LIMIT  = 400         
_DISPLAY_WIDTH   = 72

_OA_ID_PREFIX = "https://openalex.org/"


# ---------------------------------------------------------------------------
# LAYOUT CONFIGURATIONS
# ---------------------------------------------------------------------------

def _supports_colour() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class _Colour:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    YELLOW  = "\033[33m"
    GREEN   = "\033[32m"
    RED     = "\033[31m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    WHITE   = "\033[97m"


def styled(text: object, *codes: str) -> str:
    """Wraps text in ANSI escape codes if the terminal supports colour."""
    if not _supports_colour():
        return str(text)
    return "".join(codes) + str(text) + _Colour.RESET


def rule(char: str = "─", width: int = _DISPLAY_WIDTH) -> str:
    return styled(char * width, _Colour.DIM)


def truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# HTTP SESSION 
# ---------------------------------------------------------------------------

def _build_session(email: Optional[str] = None) -> requests.Session:
    """Returns a requests Session with retry logic and optional polite-pool header.

    OpenAlex routes requests that include a contact email to a faster pool.
    No account or API key is required.
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist={500, 502, 503, 504},
        allowed_methods={"GET"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    ua = "litgraph/1.0 (https://github.com/your-repo/litgraph)"
    if email:
        ua += f"; mailto:{email}"
    session.headers["User-Agent"] = ua
    return session


# ---------------------------------------------------------------------------
# DATA MODEL
# ---------------------------------------------------------------------------

@dataclass
class Paper:
    """Represents a single paper node in the citation graph."""
    paper_id:       str
    title:          str             = "Unknown"
    year:           Optional[int]   = None
    authors:        list[str]       = field(default_factory=list)
    citation_count: int             = 0
    abstract:       str             = ""
    venue:          str             = ""
    is_seed:        bool            = False
    doi:            str             = ""
    arxiv:          str             = ""

    # Computed after graph construction:
    pagerank:       float           = 0.0
    in_degree:      int             = 0
    out_degree:     int             = 0

    @classmethod
    def from_api_response(cls, raw: dict, *, is_seed: bool = False) -> "Paper":
        """Constructs a Paper from an OpenAlex Work API dict."""
        return cls(
            paper_id       = _oa_short_id(raw.get("id") or ""),
            title          = raw.get("title") or "Unknown",
            year           = raw.get("publication_year"),
            authors        = _oa_authors(raw),
            citation_count = raw.get("cited_by_count") or 0,
            abstract       = _oa_abstract(raw)[:_ABSTRACT_LIMIT],
            venue          = _oa_venue(raw),
            is_seed        = is_seed,
            doi            = _oa_doi(raw),
            arxiv          = _oa_arxiv(raw),
        )

    @classmethod
    def stub_from_api(cls, raw: dict) -> "Paper":
        """Constructs a lightweight Paper from an OpenAlex Work stub."""
        return cls(
            paper_id       = _oa_short_id(raw.get("id") or ""),
            title          = raw.get("title") or "Unknown",
            year           = raw.get("publication_year"),
            authors        = _oa_authors(raw),
            citation_count = raw.get("cited_by_count") or 0,
            venue          = _oa_venue(raw),
        )


# ---------------------------------------------------------------------------
# OPENALEX FIELD HELPERS
# ---------------------------------------------------------------------------

def _oa_short_id(full_id: str) -> str:
    """Strips the OpenAlex URI prefix, returning just the Work ID (e.g. W2741809807)."""
    return full_id.removeprefix(_OA_ID_PREFIX)


def _oa_authors(raw: dict) -> list[str]:
    """Extracts up to 5 author display names from an OpenAlex authorships list."""
    return [
        a.get("author", {}).get("display_name") or "Unknown"
        for a in (raw.get("authorships") or [])[:5]
    ]


def _oa_venue(raw: dict) -> str:
    """Extracts journal/conference name from primary_location."""
    loc    = raw.get("primary_location") or {}
    source = loc.get("source") or {}
    return source.get("display_name") or ""


def _oa_doi(raw: dict) -> str:
    """Extracts a bare DOI (without the https://doi.org/ prefix)."""
    doi = (raw.get("ids") or {}).get("doi") or ""
    return doi.removeprefix("https://doi.org/")


def _oa_arxiv(raw: dict) -> str:
    """Extracts a bare ArXiv ID."""
    arxiv = (raw.get("ids") or {}).get("arxiv") or ""
    return arxiv.removeprefix("https://arxiv.org/abs/")


def _oa_abstract(raw: dict) -> str:
    """
    Reconstructs an abstract from OpenAlex's inverted-index format.

    OpenAlex stores abstracts as ``{word: [position, ...], ...}`` to save
    space.  We invert this back to a readable string.
    """
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


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class OpenAlexClient:
    """Thin wrapper around the OpenAlex Works API.

    No API key or account is required.  Passing an *email* opts into the
    faster "polite" request pool.
    """

    def __init__(self, email: Optional[str] = None) -> None:
        self._session = _build_session(email)

    def fetch_paper(self, work_id: str) -> Optional[dict]:
        """Fetches full metadata for a single Work ID (e.g. W2741809807, DOI, URL).

        Accepts:
            W<digits>                   OpenAlex Work ID
            doi:<value>                 DOI lookup
            https://doi.org/<value>     DOI URL
            https://openalex.org/W...   Full OpenAlex URI
        """
        # Normalise: if the caller passed a short ID, build the full URL.
        if work_id.startswith("W") and work_id[1:].isdigit():
            url = f"{_API_BASE}/works/{work_id}"
        elif work_id.lower().startswith("doi:"):
            url = f"{_API_BASE}/works/doi:{work_id[4:]}"
        elif work_id.startswith("https://"):
            url = f"{_API_BASE}/works/{work_id}"
        else:
            url = f"{_API_BASE}/works/{work_id}"
        return self._get(url, params={"select": _FULL_SELECT})

    def fetch_papers_by_ids(self, work_ids: list[str]) -> list[dict]:
        """Batches fetch up to 50 Work stubs in a single API call.

        OpenAlex supports filter=openalex_id:<id1>|<id2>|... which is far
        more efficient than individual fetches for building stub nodes.
        """
        if not work_ids:
            return []
        # Normalise IDs to full URIs (required by the filter param)
        full_ids = [
            f"{_OA_ID_PREFIX}{wid}" if not wid.startswith("http") else wid
            for wid in work_ids[:50]
        ]
        filter_str = "openalex_id:" + "|".join(full_ids)
        result = self._get(
            f"{_API_BASE}/works",
            params={"filter": filter_str, "select": _STUB_SELECT, "per_page": 50},
        )
        return (result or {}).get("results", [])

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Searches for works matching *query*. Returns a list of raw dicts."""
        result = self._get(
            f"{_API_BASE}/works",
            params={"search": query, "select": _STUB_SELECT, "per_page": limit},
        )
        return (result or {}).get("results", [])

    def _get(
        self,
        url: str,
        params: Optional[dict] = None,
        *,
        _attempt: int = 0,
    ) -> Optional[dict]:
        """Executes a GET request, handling rate limits with exponential back-off."""
        try:
            resp = self._session.get(url, params=params, timeout=_REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            print(styled(f" Network error: {exc}", _Colour.RED), file=sys.stderr)
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429:
            if _attempt >= _MAX_RETRIES:
                print(styled(" Rate limit retries exhausted.", _Colour.RED), file=sys.stderr)
                return None
            wait = _RATE_LIMIT_WAIT * (2 ** _attempt)
            print(styled(f" Rate limited — waiting {wait}s (attempt {_attempt + 1})", _Colour.YELLOW))
            time.sleep(wait)
            return self._get(url, params, _attempt=_attempt + 1)

        if resp.status_code == 404:
            print(styled(f" Not found: {url}", _Colour.RED), file=sys.stderr)
        else:
            print(styled(f" HTTP {resp.status_code}: {url}", _Colour.RED), file=sys.stderr)

        return None


# ---------------------------------------------------------------------------
# GRAPH CONSTRUCTION
# ---------------------------------------------------------------------------

EdgeType = str  


def build_graph(
    seed_ids: list[str],
    *,
    depth: int = 1,
    max_nodes: int = 100,
    client: OpenAlexClient,
) -> nx.DiGraph:
    """
    Builds a directed citation graph by BFS from *seed_ids*.

    Nodes carry all :class:`Paper` fields as attributes.
    Edges carry an ``edge_type`` attribute: ``"references"`` (A→B means A
    cites B).  OpenAlex does not expose incoming citation lists per-work in
    the free tier, so edges are references only.

    Args:
        seed_ids:  List of OpenAlex Work IDs (W<digits>), DOIs (doi:…),
                   or full OpenAlex URIs.
        depth:     BFS expansion depth.  ``depth=1`` fetches direct neighbours
                   only; ``depth=2`` fetches one further hop (slow).
        max_nodes: Stop expanding once the graph reaches this many nodes.
        client:    Configured :class:`OpenAlexClient`.

    Returns:
        A :class:`networkx.DiGraph` ready for analysis or serialisation.
    """
    graph: nx.DiGraph = nx.DiGraph()
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque((pid, 0) for pid in seed_ids)

    print(styled("\n  Building citation graph", _Colour.BOLD))
    print(styled(
        f"  Seeds: {len(seed_ids)}  |  Depth: {depth}  |  Max nodes: {max_nodes}\n",
        _Colour.DIM,
    ))

    while queue and len(graph) < max_nodes:
        paper_id, current_depth = queue.popleft()

        if paper_id in visited:
            continue
        visited.add(paper_id)

        _log_fetch(paper_id, len(graph), current_depth)
        raw = client.fetch_paper(paper_id)
        time.sleep(_POLITE_DELAY)

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
    graph:     nx.DiGraph,
    raw:       dict,
    source_id: str,
    client:    OpenAlexClient,
) -> list[str]:
    """
    Register reference stubs in the graph, batch-fetch their metadata, and
    return their short IDs for BFS enqueueing.

    OpenAlex exposes references via ``referenced_works``, which is a list of
    full Work URIs.  We strip them to short IDs, batch-fetch their metadata
    (up to 50 per API call), and add edges: source_id → ref_id.
    """
    ref_uris: list[str] = raw.get("referenced_works") or []
    if not ref_uris:
        return []

    ref_ids = [_oa_short_id(uri) for uri in ref_uris if uri]

    # Batch-fetch stubs for any IDs not yet in the graph.
    unknown_ids = [rid for rid in ref_ids if rid not in graph]
    if unknown_ids:
        stubs = client.fetch_papers_by_ids(unknown_ids)
        time.sleep(_POLITE_DELAY)
        for stub_raw in stubs:
            if stub_raw.get("id"):
                stub = Paper.stub_from_api(stub_raw)
                _ensure_stub_node(graph, stub.paper_id, stub_raw)

    # Add edges and collect neighbours (only IDs that ended up in the graph).
    neighbour_ids: list[str] = []
    for rid in ref_ids:
        if rid not in graph:
            # Stub fetch may have missed it (e.g. retracted); add a minimal node.
            graph.add_node(rid, title="Unknown", year=None, authors=[],
                           citation_count=0, abstract="", venue="",
                           is_seed=False, doi="", arxiv="",
                           pagerank=0.0, in_degree=0, out_degree=0)
        graph.add_edge(source_id, rid, edge_type="references")
        neighbour_ids.append(rid)

    return neighbour_ids


def _ensure_stub_node(graph: nx.DiGraph, paper_id: str, raw: dict) -> None:
    """Add a lightweight node for a neighbour paper if not already present."""
    if paper_id not in graph:
        stub = Paper.stub_from_api(raw)
        _add_paper_node(graph, stub)


def _log_fetch(paper_id: str, node_count: int, depth: int) -> None:
    print(
        f"  {styled('→', _Colour.CYAN)} "
        f"[{node_count:>3}] "
        f"{styled(truncate(paper_id, 25), _Colour.DIM)} "
        f"depth={depth}"
    )


def _print_graph_summary(graph: nx.DiGraph) -> None:
    print(
        f"\n  {styled('✓', _Colour.GREEN)} "
        f"Graph complete: "
        f"{styled(len(graph.nodes), _Colour.BOLD)} nodes, "
        f"{styled(len(graph.edges), _Colour.BOLD)} edges\n"
    )


# ---------------------------------------------------------------------------
# GRAPH METRICS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GraphMetrics:
    pagerank:   dict[str, float]
    in_degree:  dict[str, int]
    out_degree: dict[str, int]


def compute_metrics(graph: nx.DiGraph) -> GraphMetrics:
    """Compute PageRank and degree centrality for every node."""
    try:
        pagerank = nx.pagerank(graph, alpha=0.85)
    except nx.PowerIterationFailedConvergence:
        pagerank = {n: 0.0 for n in graph}

    return GraphMetrics(
        pagerank   = pagerank,
        in_degree  = dict(graph.in_degree()),
        out_degree = dict(graph.out_degree()),
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def save_graph(graph: nx.DiGraph, path: Path) -> None:
    """Serialise the graph (nodes + edges) to a JSON file at *path*."""
    metrics = compute_metrics(graph)

    nodes: list[dict] = []
    for node_id, attrs in graph.nodes(data=True):
        nodes.append({
            "id":         node_id,
            **attrs,
            "pagerank":   round(metrics.pagerank.get(node_id, 0.0), 8),
            "in_degree":  metrics.in_degree.get(node_id, 0),
            "out_degree": metrics.out_degree.get(node_id, 0),
        })

    edges: list[dict] = [
        {"source": s, "target": t, **data}
        for s, t, data in graph.edges(data=True)
    ]

    path.write_text(json.dumps({"nodes": nodes, "edges": edges}, indent=2), encoding="utf-8")
    print(styled(f"  Saved → {path}", _Colour.GREEN))


def load_graph(path: Path) -> nx.DiGraph:
    """Deserialise a graph previously written by :func:`save_graph`."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    graph   = nx.DiGraph()

    for node in payload["nodes"]:
        node_copy = dict(node)
        node_id   = node_copy.pop("id")
        graph.add_node(node_id, **node_copy)

    for edge in payload["edges"]:
        graph.add_edge(
            edge["source"],
            edge["target"],
            edge_type=edge.get("edge_type", ""),
        )

    return graph


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_paper(
    node_id: str,
    attrs:   dict,
    *,
    rank:          Optional[int]  = None,
    show_abstract: bool           = False,
) -> None:
    """Pretty-print a single paper entry to stdout."""
    prefix    = f"  {styled(f'#{rank}', _Colour.DIM)} " if rank else "  "
    seed_tag  = styled(" [SEED]", _Colour.YELLOW) if attrs.get("is_seed") else ""
    year_str  = styled(f" {attrs.get('year', '?')}", _Colour.BLUE)
    title_str = styled(truncate(attrs.get("title", "?"), 68), _Colour.WHITE, _Colour.BOLD)

    print(f"{prefix}{title_str}{seed_tag}{year_str}")

    meta_parts: list[str] = []
    authors = attrs.get("authors", [])
    if authors:
        author_line = ", ".join(authors[:3])
        if len(authors) > 3:
            author_line += " et al."
        meta_parts.append(styled(author_line, _Colour.DIM))
    if attrs.get("venue"):
        meta_parts.append(styled(attrs["venue"], _Colour.DIM))
    meta_parts.append(styled(f"{attrs.get('citation_count', 0)} citations", _Colour.CYAN))
    if attrs.get("pagerank"):
        meta_parts.append(styled(f"PR={attrs['pagerank']:.5f}", _Colour.MAGENTA))

    print(f"  {'  '.join(meta_parts)}")

    if show_abstract and attrs.get("abstract"):
        _print_wrapped(attrs["abstract"], indent=2, width=68)

    links: list[str] = []
    if attrs.get("doi"):
        links.append(f"DOI: https://doi.org/{attrs['doi']}")
    if attrs.get("arxiv"):
        links.append(f"arXiv: https://arxiv.org/abs/{attrs['arxiv']}")
    links.append(f"OA: https://openalex.org/{node_id}")
    print(f"  {styled(' | '.join(links), _Colour.DIM)}")


def _print_wrapped(text: str, *, indent: int, width: int) -> None:
    """Print *text* word-wrapped at *width* with *indent* leading spaces."""
    pad   = " " * indent
    words = text.split()
    line: list[str] = []
    for word in words:
        if sum(len(w) + 1 for w in line) + len(word) > width:
            print(f"{pad}{styled(' '.join(line), _Colour.DIM)}")
            line = [word]
        else:
            line.append(word)
    if line:
        print(f"{pad}{styled(' '.join(line), _Colour.DIM)}")


# ---------------------------------------------------------------------------
# SUB-COMMANDS
# ---------------------------------------------------------------------------

def cmd_search(args: argparse.Namespace) -> None:
    client  = OpenAlexClient(email=getattr(args, "email", None))
    results = client.search(args.query, limit=args.limit)

    print(rule())
    print(styled(f'  Search: "{args.query}"', _Colour.CYAN, _Colour.BOLD))
    print(rule())

    if not results:
        print(styled("  No results found.", _Colour.RED))
        return

    print(f"\n  {styled(len(results), _Colour.BOLD)} results — use these IDs as --seeds:\n")
    for i, raw in enumerate(results, start=1):
        if not raw.get("id"):
            continue
        stub = Paper.stub_from_api(raw)
        print_paper(stub.paper_id, asdict(stub), rank=i)
        print()

    print(rule())


def cmd_explore(args: argparse.Namespace) -> None:
    client = OpenAlexClient(email=getattr(args, "email", None))
    output = Path(args.output)

    print(rule())
    print(styled("  litgraph explore", _Colour.CYAN, _Colour.BOLD))
    print(rule())

    graph = build_graph(
        args.seeds,
        depth     = args.depth,
        max_nodes = args.max_nodes,
        client    = client,
    )
    save_graph(graph, output)

    print(f"\n  {styled('Next steps:', _Colour.BOLD)}")
    print(f"  {styled(f'litgraph top {output}', _Colour.CYAN)}        — most influential papers")
    print(f"  {styled(f'litgraph stats {output}', _Colour.CYAN)}      — graph statistics")
    print(f"  {styled(f'litgraph show {output} <id>', _Colour.CYAN)}  — paper details\n")


def cmd_stats(args: argparse.Namespace) -> None:
    graph   = load_graph(Path(args.file))
    metrics = compute_metrics(graph)

    seed_count = sum(1 for _, d in graph.nodes(data=True) if d.get("is_seed"))
    years      = [d["year"] for _, d in graph.nodes(data=True) if d.get("year")]
    total_cit  = sum(d.get("citation_count", 0) for _, d in graph.nodes(data=True))
    avg_cit    = total_cit / len(graph) if graph else 0.0

    print(rule())
    print(styled("  litgraph stats", _Colour.CYAN, _Colour.BOLD))
    print(rule())

    def row(label: str, value: object) -> None:
        print(f"\n  {styled(label, _Colour.BOLD):<30} {value}")

    row("Nodes",               len(graph.nodes))
    row("Edges",               len(graph.edges))
    row("Seed papers",         seed_count)
    if years:
        row("Year range",      f"{min(years)} – {max(years)}")
    row("Total citations",     f"{total_cit:,}")
    row("Avg citations/paper", f"{avg_cit:.1f}")
    row("Graph density",       f"{nx.density(graph):.4f}")

    wcc = list(nx.weakly_connected_components(graph))
    row("Connected components", len(wcc))
    if wcc:
        row("Largest component", f"{max(len(c) for c in wcc)} nodes")

    top_id   = max(metrics.pagerank, key=metrics.pagerank.__getitem__)
    top_data = graph.nodes[top_id]
    print(f"\n  {styled('Top PageRank paper:', _Colour.BOLD)}")
    print(f"  {styled(truncate(top_data.get('title', '?'), 65), _Colour.WHITE)}")
    print(
        f"  {styled(top_data.get('year', '?'), _Colour.BLUE)}  "
        f"{styled(f'PR={metrics.pagerank[top_id]:.5f}', _Colour.MAGENTA)}"
    )
    print(f"\n{rule()}\n")


def cmd_top(args: argparse.Namespace) -> None:
    graph   = load_graph(Path(args.file))
    metrics = compute_metrics(graph)
    nodes   = list(graph.nodes(data=True))

    sort_map = {
        "pagerank":  (lambda nid, data: metrics.pagerank.get(nid, 0.0), "by PageRank"),
        "citations": (lambda nid, data: data.get("citation_count", 0),  "by citation count"),
        "year":      (lambda nid, data: data.get("year") or 0,          "by year (newest first)"),
    }
    key_fn, label = sort_map[args.by]
    ranked = sorted(nodes, key=lambda x: key_fn(x[0], x[1]), reverse=True)

    n = min(args.n, len(ranked))
    print(rule())
    print(styled(f"  Top {n} papers {label}", _Colour.CYAN, _Colour.BOLD))
    print(rule())
    print()

    for rank, (node_id, attrs) in enumerate(ranked[:n], start=1):
        enriched = {
            **attrs,
            "pagerank":   metrics.pagerank.get(node_id, 0.0),
            "in_degree":  metrics.in_degree.get(node_id, 0),
            "out_degree": metrics.out_degree.get(node_id, 0),
        }
        print_paper(node_id, enriched, rank=rank)
        print()

    print(rule())


def cmd_show(args: argparse.Namespace) -> None:
    graph   = load_graph(Path(args.file))
    node_id = _resolve_paper_id(graph, args.paper_id)

    if node_id is None:
        return

    attrs   = dict(graph.nodes[node_id])
    metrics = compute_metrics(graph)

    in_neighbours  = list(graph.predecessors(node_id))
    out_neighbours = list(graph.successors(node_id))

    print(rule())
    print(styled("  Paper Detail", _Colour.CYAN, _Colour.BOLD))
    print(rule())
    print()

    print_paper(
        node_id,
        {
            **attrs,
            "pagerank":   metrics.pagerank.get(node_id, 0.0),
            "in_degree":  metrics.in_degree.get(node_id, 0),
            "out_degree": metrics.out_degree.get(node_id, 0),
        },
        show_abstract=True,
    )

    _print_neighbour_list(graph, in_neighbours,  label="Cited by")
    _print_neighbour_list(graph, out_neighbours, label="References")

    print(f"\n{rule()}\n")


def _resolve_paper_id(graph: nx.DiGraph, query: str) -> Optional[str]:
    """Return the node ID matching *query* (exact ID or title fragment)."""
    if query in graph:
        return query

    matches = [
        (nid, d)
        for nid, d in graph.nodes(data=True)
        if query.lower() in (d.get("title") or "").lower()
    ]

    if not matches:
        print(styled(f"\n  Paper not found: {query}\n", _Colour.RED), file=sys.stderr)
        print(styled("  Tip: use 'litgraph top <file>' to browse IDs\n", _Colour.DIM), file=sys.stderr)
        return None

    if len(matches) == 1:
        return matches[0][0]

    print(styled(f'\n  Multiple matches for "{query}":\n', _Colour.YELLOW))
    for nid, data in matches[:10]:
        print(f"  {styled(nid[:20], _Colour.DIM)}  {truncate(data.get('title', '?'), 60)}")
    print()
    return None


def _print_neighbour_list(
    graph: nx.DiGraph,
    neighbour_ids: list[str],
    *,
    label: str,
    limit: int = 8,
) -> None:
    if not neighbour_ids:
        return
    print(f"\n  {styled(f'{label} ({len(neighbour_ids)} in graph):', _Colour.BOLD)}")
    for npid in neighbour_ids[:limit]:
        nd = graph.nodes.get(npid, {})
        print(
            f"  {styled('·', _Colour.DIM)} "
            f"{truncate(nd.get('title', '?'), 62)} "
            f"{styled(nd.get('year', '?'), _Colour.BLUE)}"
        )
    if len(neighbour_ids) > limit:
        print(styled(f"  … and {len(neighbour_ids) - limit} more", _Colour.DIM))


# ---------------------------------------------------------------------------
# CLI DEFINITION
# ---------------------------------------------------------------------------

_EPILOG = """examples:
  Search for seed papers:
    litgraph search "digital twin ICS security" --limit 10

  Build a graph from seeds (OpenAlex Work IDs or DOIs):
    litgraph explore --seeds W2741809807
    litgraph explore --seeds W2741809807 doi:10.1145/3320269.3384724 \
                     --depth 1 --max-nodes 80 --output my_graph.json

  Inspect the graph:
    litgraph stats  my_graph.json
    litgraph top    my_graph.json --by pagerank --n 20
    litgraph top    my_graph.json --by citations
    litgraph show   my_graph.json W2741809807
    litgraph show   my_graph.json "water treatment"  # title fragment

  Speed up with the OpenAlex polite pool (no signup, just your email):
    litgraph search "ICS security" --email you@university.edu
    litgraph explore --seeds W2741809807 --email you@university.edu
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="litgraph",
        description="Citation graph explorer for academic literature",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EPILOG,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── search ────────────────────────────────────────────────────────
    p_search = sub.add_parser("search", help="Search for papers by keyword")
    p_search.add_argument("query",                    help="Search query string")
    p_search.add_argument("--limit",  type=int, default=10, help="Max results (default: 10)")
    p_search.add_argument("--email", dest="email", default=None,
        help="Your email — opts into OpenAlex polite (faster) pool")
    p_search.set_defaults(func=cmd_search)

    # ── explore ───────────────────────────────────────────────────────
    p_explore = sub.add_parser("explore", help="Crawl and save a citation graph")
    p_explore.add_argument(
        "--seeds", nargs="+", required=True,
        help="OpenAlex Work IDs (W<digits>), doi:<value>, or full OpenAlex URIs",
    )
    p_explore.add_argument(
        "--depth", type=int, default=1,
        help="BFS expansion depth (default: 1).  depth=2 is significantly slower.",
    )
    p_explore.add_argument(
        "--max-nodes", dest="max_nodes", type=int, default=100,
        help="Stop expanding after this many nodes (default: 100)",
    )
    p_explore.add_argument(
        "--output", default="graph_data.json",
        help="Output JSON file (default: graph_data.json)",
    )
    p_explore.add_argument("--email", dest="email", default=None,
        help="Your email — opts into OpenAlex polite (faster) pool")
    p_explore.set_defaults(func=cmd_explore)

    # ── stats ─────────────────────────────────────────────────────────
    p_stats = sub.add_parser("stats", help="Print graph-level statistics")
    p_stats.add_argument("file", help="Path to graph_data.json")
    p_stats.set_defaults(func=cmd_stats)

    # ── top ───────────────────────────────────────────────────────────
    p_top = sub.add_parser("top", help="List most influential papers")
    p_top.add_argument("file", help="Path to graph_data.json")
    p_top.add_argument(
        "--by", choices=["pagerank", "citations", "year"], default="pagerank",
        help="Sort criterion (default: pagerank)",
    )
    p_top.add_argument("--n", type=int, default=15, help="Number of papers to display (default: 15)")
    p_top.set_defaults(func=cmd_top)

    # ── show ──────────────────────────────────────────────────────────
    p_show = sub.add_parser("show", help="Inspect a single paper")
    p_show.add_argument("file",     help="Path to graph_data.json")
    p_show.add_argument("paper_id", help="OpenAlex Work ID or title fragment")
    p_show.set_defaults(func=cmd_show)

    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()