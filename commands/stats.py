import argparse
import networkx as nx

from commands.base import GraphFileCommand
from graph.metrics import compute_metrics
from core.style import rule, styled, truncate, Colour


def _stats_rows(graph):
    seed_count = sum(1 for _, d in graph.nodes(data=True) if d.get("is_seed"))
    years = [d["year"] for _, d in graph.nodes(data=True) if d.get("year")]
    total_cit = sum(d.get("citation_count", 0) for _, d in graph.nodes(data=True))
    avg_cit = total_cit / len(graph) if graph else 0.0

    rows = [
        ("Nodes", len(graph.nodes)),
        ("Edges", len(graph.edges)),
        ("Seed papers", seed_count),
        ("Total citations", f"{total_cit:,}"),
        ("Avg citations/paper", f"{avg_cit:.1f}"),
        ("Graph density", f"{nx.density(graph):.4f}"),
    ]
    if years:
        rows.insert(4, ("Year range", f"{min(years)} – {max(years)}"))

    wcc = list(nx.weakly_connected_components(graph))
    rows.append(("Connected components", len(wcc)))
    if wcc:
        rows.append(("Largest component", f"{max(len(c) for c in wcc)} nodes"))
    return rows


def _print_top_pagerank(graph, metrics):
    top_id = max(metrics.pagerank, key=metrics.pagerank.__getitem__)
    top_data = graph.nodes[top_id]
    print(f"\n  {styled('Top PageRank paper:', Colour.BOLD)}")
    print(f"  {styled(truncate(top_data.get('title', '?'), 65), Colour.WHITE)}")
    print(
        f"  {styled(top_data.get('year', '?'), Colour.BLUE)}  "
        f"{styled(f'PR={metrics.pagerank[top_id]:.5f}', Colour.MAGENTA)}"
    )


def run_stats(graph):
    metrics = compute_metrics(graph)

    print(rule())
    print(styled("  litgraph stats", Colour.CYAN, Colour.BOLD))
    print(rule())

    for label, value in _stats_rows(graph):
        print(f"\n  {styled(label, Colour.BOLD):<30} {value}")

    _print_top_pagerank(graph, metrics)
    print(f"\n{rule()}\n")


class StatsCommand(GraphFileCommand):
    name = "stats"
    help = "Print graph-level statistics"

    def run(self, args):
        run_stats(self.get_graph(args))
