"""Command-line entry point for Ariadne."""

import argparse
import sys

from pathlib import Path

from ariadne.eval import evaluate_paths, format_report
from ariadne.extraction import AnthropicExtractionProvider, ExtractionProvider
from ariadne.graph_store import InMemoryGraphStore
from ariadne.pipeline import run_extraction_pipeline
from ariadne.resolution import resolve
from ariadne.validation import validate
from ariadne.vault import render_vault

SUBCOMMANDS = ("extract", "eval", "validate", "resolve")


def _default_provider() -> ExtractionProvider:
    """Build the live extraction provider. Kept as a seam for tests to patch."""
    return AnthropicExtractionProvider()


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
