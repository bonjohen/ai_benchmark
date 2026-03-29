"""Graph viewer for AI Benchmark collection graphs.

Renders the TOML-defined source collection graphs using networkx + matplotlib.

Usage:
    python scripts/view_graph.py                     # All three graphs side-by-side
    python scripts/view_graph.py primary              # Single graph
    python scripts/view_graph.py secondary discovery   # Two graphs
    python scripts/view_graph.py --combined           # All graphs merged into one view
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_DIR = Path(__file__).resolve().parent.parent / "ai_benchmark" / "config"

GRAPH_FILES = {
    "primary": CONFIG_DIR / "graph_primary.toml",
    "secondary": CONFIG_DIR / "graph_secondary.toml",
    "discovery": CONFIG_DIR / "graph_discovery.toml",
}

# Visual styling per node type
NODE_COLORS = {
    "control": "#2d2d2d",
    "source": "#1f77b4",
    "page": "#aec7e8",
}
NODE_SIZES = {
    "control": 800,
    "source": 600,
    "page": 300,
}
NODE_FONT_SIZES = {
    "control": 9,
    "source": 7,
    "page": 5,
}

# Edge styling per relationship
EDGE_STYLES = {
    "initiates": {"color": "#666666", "style": "solid", "width": 1.5},
    "monitors": {"color": "#1f77b4", "style": "solid", "width": 1.0},
    "produces": {"color": "#2ca02c", "style": "solid", "width": 1.0},
    "confirms": {"color": "#d62728", "style": "dashed", "width": 1.5},
    "supplements": {"color": "#ff7f0e", "style": "dotted", "width": 1.2},
    "feeds_into": {"color": "#9467bd", "style": "dashed", "width": 1.2},
}

# Classification → title color
CLASSIFICATION_COLORS = {
    "primary": "#1f77b4",
    "secondary": "#ff7f0e",
    "discovery-only": "#2ca02c",
}


def load_graph(path: Path) -> tuple[dict, nx.DiGraph]:
    """Load a TOML graph file into a networkx DiGraph."""
    with open(path, "rb") as f:
        data = tomllib.load(f)

    meta = data.get("graph", {})
    G = nx.DiGraph()

    for node in data.get("nodes", []):
        G.add_node(
            node["id"],
            label=node.get("label", node["id"]),
            node_type=node.get("type", "page"),
            trust_rating=node.get("trust_rating"),
            organization=node.get("organization"),
            collection_method=node.get("collection_method"),
            priority=node.get("priority", False),
        )

    for edge in data.get("edges", []):
        G.add_edge(
            edge["source"],
            edge["target"],
            relationship=edge.get("relationship", "unknown"),
        )

    return meta, G


def layout_graph(G: nx.DiGraph) -> dict:
    """Compute a hierarchical layout: START at top, sources middle, pages below, END at bottom."""
    pos = {}
    control_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "control"]
    source_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "source"]
    page_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "page"]

    # Group pages by their parent source
    source_pages: dict[str, list[str]] = {s: [] for s in source_nodes}
    for page in page_nodes:
        for pred in G.predecessors(page):
            if pred in source_pages:
                source_pages[pred].append(page)
                break
        else:
            # Unattached page — place after last source
            if source_nodes:
                source_pages[source_nodes[-1]].append(page)

    # Y layers
    y_start, y_source, y_page, y_end = 3.0, 2.0, 0.5, -0.5

    # Place START and END
    for node in control_nodes:
        if node == "START":
            pos[node] = (0.0, y_start)
        else:
            pos[node] = (0.0, y_end)

    # Spread sources evenly
    n_sources = len(source_nodes)
    if n_sources > 0:
        x_span = max(n_sources * 2.0, 6.0)
        for i, src in enumerate(source_nodes):
            x = -x_span / 2 + (i + 0.5) * (x_span / n_sources)
            pos[src] = (x, y_source)

            # Pages beneath their source, fanned out
            pages = source_pages[src]
            n_pages = len(pages)
            if n_pages > 0:
                page_span = max(1.5, n_pages * 0.6)
                src_x = x
                for j, pg in enumerate(pages):
                    px = src_x - page_span / 2 + (j + 0.5) * (page_span / n_pages)
                    # Stagger Y slightly for readability
                    py = y_page - (j % 2) * 0.3
                    pos[pg] = (px, py)

    # Center START/END on the x-axis midpoint
    if source_nodes:
        all_x = [pos[s][0] for s in source_nodes]
        mid_x = (min(all_x) + max(all_x)) / 2
        for cn in control_nodes:
            pos[cn] = (mid_x, pos[cn][1])

    return pos


def draw_graph(ax: plt.Axes, meta: dict, G: nx.DiGraph) -> None:
    """Draw a single graph onto a matplotlib Axes."""
    pos = layout_graph(G)

    classification = meta.get("classification", "primary")
    title_color = CLASSIFICATION_COLORS.get(classification, "#333333")
    title = meta.get("name", "Graph")
    subtitle = f"{meta.get('source_count', '?')} sources, {meta.get('page_count', '?')} pages"
    ax.set_title(f"{title}\n{subtitle}", fontsize=11, fontweight="bold", color=title_color)

    # Draw edges grouped by relationship
    for rel, style in EDGE_STYLES.items():
        edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("relationship") == rel]
        if edges:
            nx.draw_networkx_edges(
                G,
                pos,
                edgelist=edges,
                ax=ax,
                edge_color=style["color"],
                style=style["style"],
                width=style["width"],
                alpha=0.6,
                arrows=True,
                arrowsize=8,
                connectionstyle="arc3,rad=0.05",
            )

    # Draw nodes grouped by type
    for ntype, color in NODE_COLORS.items():
        nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == ntype]
        if nodes:
            # Priority pages get a highlight ring
            if ntype == "page":
                priority_nodes = [n for n in nodes if G.nodes[n].get("priority")]
                normal_nodes = [n for n in nodes if not G.nodes[n].get("priority")]
                if priority_nodes:
                    nx.draw_networkx_nodes(
                        G,
                        pos,
                        nodelist=priority_nodes,
                        ax=ax,
                        node_color="#ffdd57",
                        node_size=NODE_SIZES[ntype] + 100,
                        edgecolors="#e6a817",
                        linewidths=1.5,
                    )
                    nx.draw_networkx_nodes(
                        G,
                        pos,
                        nodelist=priority_nodes,
                        ax=ax,
                        node_color=color,
                        node_size=NODE_SIZES[ntype],
                    )
                nodes = normal_nodes

            nx.draw_networkx_nodes(
                G,
                pos,
                nodelist=nodes,
                ax=ax,
                node_color=color,
                node_size=NODE_SIZES[ntype],
                edgecolors="white" if ntype == "control" else "none",
                linewidths=1.5 if ntype == "control" else 0,
            )

    # Labels
    for ntype, fsize in NODE_FONT_SIZES.items():
        nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == ntype]
        if nodes:
            labels = {n: G.nodes[n].get("label", n) for n in nodes}
            font_color = "white" if ntype in ("control", "source") else "#333333"
            nx.draw_networkx_labels(
                G, pos, labels, ax=ax, font_size=fsize, font_color=font_color, font_weight="bold"
            )

    ax.axis("off")


def draw_legend(fig: plt.Figure) -> None:
    """Add a shared legend to the figure."""
    import matplotlib.patches as mpatches
    import matplotlib.lines as mlines

    legend_elements = [
        mpatches.Patch(facecolor=NODE_COLORS["control"], label="Control (START/END)"),
        mpatches.Patch(facecolor=NODE_COLORS["source"], label="Source"),
        mpatches.Patch(facecolor=NODE_COLORS["page"], label="Page"),
        mpatches.Patch(facecolor="#ffdd57", edgecolor="#e6a817", label="Priority page"),
        mlines.Line2D([], [], color="#666666", linestyle="solid", label="initiates"),
        mlines.Line2D([], [], color="#1f77b4", linestyle="solid", label="monitors"),
        mlines.Line2D([], [], color="#2ca02c", linestyle="solid", label="produces"),
        mlines.Line2D([], [], color="#d62728", linestyle="dashed", label="confirms"),
        mlines.Line2D([], [], color="#ff7f0e", linestyle="dotted", label="supplements"),
        mlines.Line2D([], [], color="#9467bd", linestyle="dashed", label="feeds_into"),
    ]
    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=5,
        fontsize=8,
        frameon=True,
        fancybox=True,
        shadow=True,
    )


def main() -> None:
    args = [a.lower().replace("-", "_") for a in sys.argv[1:]]

    combined = "--combined" in args or "-c" in args
    args = [a for a in args if a not in ("--combined", "-c")]

    # Determine which graphs to show
    if args:
        selected = []
        for name in args:
            # Allow "discovery-only" or "discovery_only" or "discovery"
            if name.startswith("disc"):
                name = "discovery"
            if name in GRAPH_FILES:
                selected.append(name)
            else:
                print(f"Unknown graph: {name}. Available: {', '.join(GRAPH_FILES)}")
                sys.exit(1)
    else:
        selected = list(GRAPH_FILES.keys())

    # Load all selected graphs
    graphs = []
    for name in selected:
        path = GRAPH_FILES[name]
        if not path.exists():
            print(f"Graph file not found: {path}")
            sys.exit(1)
        meta, G = load_graph(path)
        graphs.append((name, meta, G))

    if combined:
        # Merge all into one graph with prefixed node IDs
        merged = nx.DiGraph()
        for name, meta, G in graphs:
            mapping = {}
            for node, data in G.nodes(data=True):
                new_id = f"{name}.{node}" if node not in ("START", "END") else node
                mapping[node] = new_id
                if new_id not in merged:
                    merged.add_node(new_id, **data)
            for u, v, data in G.edges(data=True):
                merged.add_edge(mapping[u], mapping[v], **data)

        fig, ax = plt.subplots(1, 1, figsize=(24, 14))
        combined_meta = {
            "name": "All Collection Sources (Combined)",
            "classification": "primary",
            "source_count": sum(m.get("source_count", 0) for _, m, _ in graphs),
            "page_count": sum(m.get("page_count", 0) for _, m, _ in graphs),
        }
        draw_graph(ax, combined_meta, merged)
        draw_legend(fig)
    else:
        n = len(graphs)
        fig, axes = plt.subplots(1, n, figsize=(8 * n, 10))
        if n == 1:
            axes = [axes]
        for ax, (name, meta, G) in zip(axes, graphs):
            draw_graph(ax, meta, G)
        draw_legend(fig)

    fig.suptitle(
        "AI Benchmark — Source Collection Graphs",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.show()


if __name__ == "__main__":
    main()
