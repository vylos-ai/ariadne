"""Command-line entry point for Ariadne."""

import argparse
import sys

from ariadne.extraction import AnthropicExtractionProvider, ExtractionProvider
from ariadne.graph_store import InMemoryGraphStore
from ariadne.pipeline import run_extraction_pipeline
from ariadne.validation import validate

SUBCOMMANDS = ("extract", "eval", "validate")


def _default_provider() -> ExtractionProvider:
    """Build the live extraction provider. Kept as a seam for tests to patch."""
    return AnthropicExtractionProvider()


def _extract(args: argparse.Namespace) -> int:
    provider = _default_provider()
    run_extraction_pipeline(args.source, args.output_dir, provider)
    print(f"ariadne extract: wrote graph + vault to {args.output_dir}")
    return 0


def _eval(args: argparse.Namespace) -> int:
    print("ariadne eval: not yet implemented")
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ariadne")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser(
        "extract", help="Extract a process graph from source material"
    )
    extract_parser.add_argument("source", help="Path to the source document")
    extract_parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to write graph.json and the vault/ into (default: output)",
    )
    extract_parser.set_defaults(func=_extract)

    eval_parser = subparsers.add_parser(
        "eval", help="Evaluate extraction/resolution quality"
    )
    eval_parser.set_defaults(func=_eval)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate provenance and graph consistency"
    )
    validate_parser.add_argument("graph", help="Path to a graph.json file")
    validate_parser.set_defaults(func=_validate)

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
