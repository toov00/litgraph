# litgraph

A CLI tool for mapping citation networks in academic subfields. Built with Python and OpenAlex.

## What It Does

This tool connects directly to the free [OpenAlex API](https://openalex.org/) to crawl and analyse citation graphs starting from a set of seed papers. It computes PageRank and degree metrics to surface the most influential work in a subfield, and saves the graph as JSON for repeated inspection. No account or API key required!

## Installation

**Requirements:** Python 3.10 or later

1. Clone or download the repository
2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
.venv\Scripts\activate      # Windows
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

**1. Find seed papers**

```bash
python litgraph.py search "digital twin ICS security" --limit 10
```

Copy the `W<digits>` IDs from the results — you'll use them in the next step.

**2. Build a citation graph**

```bash
python litgraph.py explore \
  --seeds W2741809807 W2950246967 \
  --depth 1 \
  --max-nodes 100 \
  --output my_graph.json
```

**3. Inspect the graph**

```bash
# Graph-level statistics
python litgraph.py stats my_graph.json

# Most influential papers
python litgraph.py top my_graph.json --by pagerank --n 20

# Full detail for a specific paper (ID or title fragment)
python litgraph.py show my_graph.json "water treatment"
```

## Configuration

**1. Seed IDs**

OpenAlex Work IDs are accepted in three formats:

| Format | Example |
|--------|---------|
| OpenAlex Work ID | `W2741809807` |
| DOI | `doi:10.1145/3320269.3384724` |
| Full OpenAlex URI | `https://openalex.org/W2741809807` |

**2. Explore Options**

```bash
python litgraph.py explore \
  --seeds <ID> [<ID> ...]   # One or more seed paper IDs
  --depth 1                 # BFS hop depth (default: 1)
  --max-nodes 100           # Stop expanding after this many nodes (default: 100)
  --output graph_data.json  # Output file (default: graph_data.json)
  --email you@uni.edu       # Optional: opts into OpenAlex polite (faster) pool
```

**3. Sort Options**

```bash
python litgraph.py top my_graph.json --by pagerank    # Structural influence
python litgraph.py top my_graph.json --by citations   # Raw citation count
python litgraph.py top my_graph.json --by year        # Newest first
```

## Limitations

**1. Execution Time**

Using `--depth` with any number greater than 1 allows for the fetching of more papers (substantially so!). Unfortunately, each hop requires additional API calls, so it is significantly slower than the default `--depth 1`. Start with depth 1 for most use cases.

**2. References Only**

OpenAlex does not expose per-paper incoming citation lists in its free tier. Edges in the graph represent references only (A → B means A cites B). Incoming citation counts are still fetched and displayed per paper.

**3. Network Dependency**

The tool requires an active internet connection. Papers not indexed by OpenAlex (some older or niche venue publications) may have incomplete metadata.

## Contributing

Contributions are welcome! If you find bugs, have feature suggestions, or want to improve the code, feel free to open an issue or submit a pull request.

When contributing, please:
- Update documentation if you add new features
- Keep the code readable and well-commented

## License

MIT

## Resources

- [OpenAlex API Documentation](https://docs.openalex.org/): Complete API reference
- [OpenAlex Web Search](https://openalex.org/works): Find paper IDs by browsing works
- [Semantic Scholar](https://www.semanticscholar.org/): Alternative source for finding seed paper IDs
# LITERATURE_GRAPHER
