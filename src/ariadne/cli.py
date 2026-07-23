"""Command-line entry point for Ariadne."""

import argparse
import sys

from pathlib import Path

from ariadne.eval import evaluate_paths, format_report
from ariadne.export import to_mermaid
from ariadne.extraction import ExtractionProvider, PydanticAIExtractionProvider
from ariadne.graph_store import InMemoryGraphStore
from ariadne.mcp_server import build_server
from ariadne.pipeline import run_extraction_pipeline
from ariadne.query import describe, find_nodes, path, walk, what_happens
from ariadne.resolution import resolve
from ariadne.schema import EdgeType
from ariadne.validation import validate
from ariadne.vault import render_vault

SUBCOMMANDS = ("extract", "eval", "validate", "resolve", "query", "export", "mcp")
QUERY_KINDS = ("find", "describe", "walk", "path", "what-happens")

# Exporters keyed by --format value. Mermaid is the only projection for now
# (BPMN-XML stays out of scope until someone asks for it -- see task 0017).
_EXPORTERS = {"mermaid": to_mermaid}


def _default_provider() -> ExtractionProvider:
    """Build the live extraction provider. Kept as a seam for tests to patch."""
    return PydanticAIExtractionProvider()


def _extract(args: argparse.Namespace) -> int:
    provider = _default_provider()
    run_extraction_pipeline(args.sources, args.output_dir, provider)
    print(f"ariadne extract: wrote graph + vault to {args.output_dir}")
    return 0


def _eval(args: argparse.Namespace) -> int:
    report = evaluate_paths(args.candidate, args.gold)
    print(format_report(report))
    return 0


def _validate(args: argparse.Namespace) -> int:
    store = InMemoryGraphStore()
    store.load(args.graph)
    violations = validate(store)

    if not violations:
        print("ariadne validate: no provenance violations found")
        return 0

    print(f"ariadne validate: {len(violations)} provenance violation(s) found")
    for violation in violations:
        print(f"  {violation}")
    return 1


def _resolve(args: argparse.Namespace) -> int:
    store = InMemoryGraphStore()
    store.load(args.graph)
    resolved = resolve(store)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved.save(output_dir / "graph.json")
    render_vault(resolved, output_dir / "vault")

    print(f"ariadne resolve: wrote resolved graph + vault to {output_dir}")
    return 0


def _query(args: argparse.Namespace) -> int:
    store = InMemoryGraphStore()
    store.load(args.graph)
    kind = args.kind
    rest = args.args

    if kind == "find":
        text = " ".join(rest)
        for scored in find_nodes(store, text):
            print(f"{scored.score:.2f}  {scored.node.id}")
        return 0

    if kind == "describe":
        node, facts = describe(store, rest[0])
        if node is None:
            print(f"ariadne query: no such node {rest[0]!r}")
            return 1
        print(f"{node.id} ({node.type.value})")
        for fact in facts:
            arrow = "->" if fact.direction == "out" else "<-"
            print(
                f"  {fact.edge.type.value} {arrow} {fact.neighbor.id} "
                f"({fact.neighbor_label})  evidence={fact.evidence_ids}"
            )
        return 0

    if kind == "walk":
        edge_type = EdgeType(rest[1]) if len(rest) > 1 else None
        direction = rest[2] if len(rest) > 2 else "both"
        facts = walk(store, rest[0], edge_type=edge_type, direction=direction)
        for fact in facts:
            arrow = "->" if fact.direction == "out" else "<-"
            print(f"  {fact.edge.type.value} {arrow} {fact.neighbor.id}")
        return 0

    if kind == "path":
        result = path(store, rest[0], rest[1])
        if not result.nodes:
            print(f"ariadne query: no path from {rest[0]!r} to {rest[1]!r}")
            return 1
        print(" -> ".join(node.id for node in result.nodes))
        return 0

    if kind == "what-happens":
        facts = what_happens(store, rest[0])
        for fact in facts:
            print(f"  {fact.edge.type.value} -> {fact.neighbor.id}")
        return 0

    print(f"ariadne query: unknown kind {kind!r}, expected one of {QUERY_KINDS}")
    return 1


def _export(args: argparse.Namespace) -> int:
    exporter = _EXPORTERS.get(args.format)
    if exporter is None:
        print(
            f"ariadne export: unknown format {args.format!r} "
            f"(choose from {', '.join(sorted(_EXPORTERS))})",
            file=sys.stderr,
        )
        return 1

    store = InMemoryGraphStore()
    store.load(args.graph)
    print(exporter(store))
    return 0


def _mcp(args: argparse.Namespace) -> int:
    store = InMemoryGraphStore()
    store.load(args.graph)
    server = build_server(store)
    server.run()  # blocks, serving over stdio
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ariadne")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser(
        "extract", help="Extract a process graph from source material"
    )
    extract_parser.add_argument(
        "sources", nargs="+", help="Path(s) to one or more source documents"
    )
    extract_parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to write graph.json and the vault/ into (default: output)",
    )
    extract_parser.set_defaults(func=_extract)

    eval_parser = subparsers.add_parser(
        "eval", help="Evaluate extraction/resolution quality"
    )
    eval_parser.add_argument("candidate", help="Path to the candidate graph.json")
    eval_parser.add_argument("gold", help="Path to the gold-standard graph.json")
    eval_parser.set_defaults(func=_eval)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate provenance and graph consistency"
    )
    validate_parser.add_argument("graph", help="Path to a graph.json file")
    validate_parser.set_defaults(func=_validate)

    resolve_parser = subparsers.add_parser(
        "resolve", help="Resolve duplicate/near-duplicate entities in a graph"
    )
    resolve_parser.add_argument("graph", help="Path to a graph.json file")
    resolve_parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to write the resolved graph.json and vault/ into "
        "(default: output)",
    )
    resolve_parser.set_defaults(func=_resolve)

    query_parser = subparsers.add_parser(
        "query", help="Ask a graph question (find/describe/walk/path/what-happens)"
    )
    query_parser.add_argument("graph", help="Path to a graph.json file")
    query_parser.add_argument("kind", choices=QUERY_KINDS, help="Kind of query")
    query_parser.add_argument(
        "args", nargs="*", help="Arguments for the chosen query kind"
    )
    query_parser.set_defaults(func=_query)

    export_parser = subparsers.add_parser(
        "export", help="Render a projection (e.g. mermaid) from a graph.json"
    )
    export_parser.add_argument("graph", help="Path to a graph.json file")
    export_parser.add_argument(
        "--format",
        default="mermaid",
        help="Projection format to render (default: mermaid)",
    )
    export_parser.set_defaults(func=_export)

    mcp_parser = subparsers.add_parser(
        "mcp", help="Serve the query layer as an MCP server over stdio"
    )
    mcp_parser.add_argument("graph", help="Path to a graph.json file")
    mcp_parser.set_defaults(func=_mcp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
