"""Shared fuzzy label-matching logic used by eval and entity resolution.

Both the eval harness (matching candidate nodes to gold nodes) and entity
resolution (clustering duplicate/near-duplicate nodes) need to decide whether
two nodes' human-readable labels refer to the same thing. Kept here so the
matching rule has exactly one definition (CLAUDE.md: YAGNI, no duplication).
"""

from __future__ import annotations

from difflib import SequenceMatcher

from ariadne.schema import Node

# Property keys checked, in order, to find a node's human-readable label.
# Most node types use "name"; Evidence nodes use "summary"/"source" instead.
_LABEL_KEYS = ("name", "label", "summary", "source")

# Ratio threshold (difflib.SequenceMatcher) above which two normalized labels
# are considered the same entity. Simple and dependency-free -- YAGNI, no ML.
_FUZZY_MATCH_THRESHOLD = 0.85


def _node_label(node: Node) -> str:
    for key in _LABEL_KEYS:
        value = node.properties.get(key)
        if value:
            return str(value)
    return ""


def _normalize(label: str) -> str:
    return label.strip().lower()


def _labels_match(a: str, b: str) -> bool:
    a, b = _normalize(a), _normalize(b)
    if not a or not b:
        return a == b
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= _FUZZY_MATCH_THRESHOLD
