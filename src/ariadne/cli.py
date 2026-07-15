"""Command-line entry point for Ariadne."""

import argparse
import sys

SUBCOMMANDS = ("extract", "eval", "validate")


def _extract(args: argparse.Namespace) -> int:
    print("ariadne extract: not yet implemented")
    return 0


def _eval(args: argparse.Namespace) -> int:
    print("ariadne eval: not yet implemented")
    return 0


def _validate(args: argparse.Namespace) -> int:
    print("ariadne validate: not yet implemented")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ariadne")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser(
        "extract", help="Extract a process graph from source material"
    )
    extract_parser.set_defaults(func=_extract)

    eval_parser = subparsers.add_parser(
        "eval", help="Evaluate extraction/resolution quality"
    )
    eval_parser.set_defaults(func=_eval)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate provenance and graph consistency"
    )
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
