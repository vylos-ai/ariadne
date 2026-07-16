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


def _label_similarity(a: str, b: str) -> float:
    """Similarity ratio in [0.0, 1.0] between two normalized labels.

    Empty-vs-empty (or identical) labels score 1.0; empty-vs-non-empty
    scores 0.0. Otherwise, ``difflib.SequenceMatcher`` ratio.
    """
    a, b = _normalize(a), _normalize(b)
    if not a or not b:
        return 1.0 if a == b else 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _labels_match(a: str, b: str) -> bool:
    return _label_similarity(a, b) >= _FUZZY_MATCH_THRESHOLD
