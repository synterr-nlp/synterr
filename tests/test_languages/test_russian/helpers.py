"""Shared fake-token builder for the Russian handler unit tests."""

from __future__ import annotations

from synterr.core.protocol import AnalyzedToken


def make_token(
    text: str,
    pos: str = "NOUN",
    lemma: str | None = None,
    idx: int = 0,
    dep_rel: str | None = None,
    head_idx: int | None = None,
    features: dict[str, str] | None = None,
) -> AnalyzedToken:
    """Build a token without a backend: no pymorphy parse in ``extra``."""
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features=features or {},
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
    )
