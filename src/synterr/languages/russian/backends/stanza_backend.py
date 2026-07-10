"""Stanza backend for Russian language analysis.

Stanza provides high-accuracy NLP analysis using neural models trained
on SynTagRus corpus. Best accuracy but slower than alternatives.

Accuracy (SynTagRus):
    - POS: 98.06%
    - Morph features: 92.78%
    - Lemma: 97.65%
    - Dependency: 90.90% LAS

Speed: ~92 sentences/second (CPU)
Model size: ~591 MB
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.inflector import (
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_NUMBER,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# Audit fix M1/C1: pick the pymorphy parse most consistent with stanza's own
# disambiguated UD features, instead of the first lemma-matching parse in
# pymorphy's frequency order. The stored parse seeds every downstream
# inflection (NounCase, AdjCase, AdjGender, ...), so a paradigm-cell mismatch
# here silently drifts unrelated grammemes: "альтернативы" (Acc Plur) picked
# pymorphy's highest-frequency gent-sing parse, so noun_case's Case-only
# inflect() started from the wrong number too ("альтернативой" — Ins
# *singular*, not just the intended case flip). Scoring is POS-class-first
# (a wrong POS class is never a useful parse to inflect from), then
# grammeme-overlap on Case/Number/Gender/VerbForm.
_UD_POS_TO_PYMORPHY: dict[str, frozenset[str]] = {
    "NOUN": frozenset({"NOUN"}),
    "PROPN": frozenset({"NOUN"}),
    "ADJ": frozenset({"ADJF", "ADJS", "COMP"}),
    "PRON": frozenset({"NPRO"}),
    "NUM": frozenset({"NUMR"}),
    "ADV": frozenset({"ADVB", "COMP", "PRED"}),
    "DET": frozenset({"NPRO", "ADJF"}),
}

# VERB/AUX tokens: VerbForm narrows which pymorphy POS class is the right
# paradigm cell (finite vs infinitive vs participle vs converb). Without a
# VerbForm feature, any verbal POS is acceptable.
_VERB_FORM_TO_PYMORPHY_POS: dict[str, frozenset[str]] = {
    "Fin": frozenset({"VERB"}),
    "Inf": frozenset({"INFN"}),
    "Part": frozenset({"PRTF", "PRTS"}),
    "Conv": frozenset({"GRND"}),
}
_ANY_VERBAL_POS = frozenset({"VERB", "INFN", "PRTF", "PRTS", "GRND"})

_FEATURE_GRAMMEME_MAPS = (
    ("Case", UD_TO_PYMORPHY_CASE),
    ("Number", UD_TO_PYMORPHY_NUMBER),
    ("Gender", UD_TO_PYMORPHY_GENDER),
)


def _expected_pymorphy_pos(upos: str, features: dict) -> frozenset[str] | None:
    """The pymorphy POS class(es) consistent with stanza's own tag, or None
    when the UD tag has no known pymorphy analogue (no signal either way)."""
    if upos in ("VERB", "AUX"):
        return _VERB_FORM_TO_PYMORPHY_POS.get(features.get("VerbForm"), _ANY_VERBAL_POS)
    return _UD_POS_TO_PYMORPHY.get(upos)


def _parse_consistency_score(parse, upos: str, features: dict) -> int:
    """Higher = more consistent with stanza's disambiguated tag.

    POS-class agreement dominates (+/-2): an inflection seeded from the
    wrong POS class is unusable regardless of how many grammemes happen to
    overlap. Each of Case/Number/Gender then contributes +1 (present and
    matching) or -1 (present and conflicting); features stanza left unset
    contribute nothing, so an unannotated token still falls back to
    pymorphy's own ranking (ties broken by candidate order == old
    lemma-match-then-first behavior).
    """
    score = 0
    expected_pos = _expected_pymorphy_pos(upos, features)
    if expected_pos is not None:
        score += 2 if parse.tag.POS in expected_pos else -2
    grammemes = parse.tag.grammemes
    for feature, mapping in _FEATURE_GRAMMEME_MAPS:
        value = features.get(feature)
        grammeme = mapping.get(value) if value else None
        if grammeme:
            score += 1 if grammeme in grammemes else -1
    return score


def _select_pymorphy_parse(parses, lemma: str, upos: str, features: dict):
    """Pick the parse most consistent with stanza's UD features.

    Restricts to lemma-matching parses first (as before), then breaks ties
    by consistency score; the first candidate wins ties, so a token with no
    usable feature signal reproduces the pre-fix behavior exactly (first
    lemma match, else pymorphy's first parse).
    """
    if not parses:
        return None

    candidates = [p for p in parses if p.normal_form == lemma]
    if not candidates:
        candidates = list(parses)

    best_idx = 0
    best_score = None
    for i, candidate in enumerate(candidates):
        score = _parse_consistency_score(candidate, upos, features)
        if best_score is None or score > best_score:
            best_score = score
            best_idx = i
    return candidates[best_idx]


class StanzaBackend:
    """Stanza-based analyzer for Russian.

    Uses Stanford NLP stanza library with Russian models trained on SynTagRus.
    Provides high accuracy POS tagging, morphological analysis, lemmatization,
    and optional dependency parsing.
    """

    name = "stanza"
    supports_depparse = True

    def __init__(self, use_depparse: bool = False, use_gpu: bool = True) -> None:
        """Initialize Stanza backend.

        Args:
            use_depparse: Enable dependency parsing (~40% slower)
            use_gpu: Use GPU acceleration
        """
        self.use_depparse = use_depparse
        self.use_gpu = use_gpu
        self._nlp = None
        self._morph = None

    @property
    def nlp(self):
        """Lazy-initialize stanza pipeline."""
        if self._nlp is None:
            import stanza

            processors = (
                "tokenize,pos,lemma,depparse"
                if self.use_depparse
                else "tokenize,pos,lemma"
            )
            self._nlp = stanza.Pipeline(
                "ru", processors=processors, verbose=False, use_gpu=self.use_gpu
            )
        return self._nlp

    @property
    def morph(self):
        """Lazy-initialize pymorphy3 for inflection."""
        if self._morph is None:
            import pymorphy3

            self._morph = pymorphy3.MorphAnalyzer()
        return self._morph

    def analyze(self, text: str) -> list[AnalyzedToken]:
        """Analyze a single sentence."""
        doc = self.nlp(text)
        tokens = []

        for sent in doc.sentences:
            for word in sent.words:
                token = self._word_to_token(word, len(tokens))
                tokens.append(token)

        return tokens

    def analyze_batch(self, texts: Sequence[str]) -> list[list[AnalyzedToken]]:
        """Analyze multiple sentences with batching (~7x faster)."""
        if not texts:
            return []

        # Track non-empty texts and their original indices
        non_empty_indices = []
        non_empty_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)

        # Initialize results with empty lists
        results: list[list[AnalyzedToken]] = [[] for _ in texts]

        if not non_empty_texts:
            return results

        # Join non-empty texts with double newline (stanza sentence boundary)
        batch_text = "\n\n".join(non_empty_texts)
        doc = self.nlp(batch_text)

        # Map stanza sentences back to original indices
        for stanza_idx, orig_idx in enumerate(non_empty_indices):
            if stanza_idx >= len(doc.sentences):
                break

            stanza_sent = doc.sentences[stanza_idx]
            tokens = []

            for i, word in enumerate(stanza_sent.words):
                token = self._word_to_token(word, i)
                tokens.append(token)

            results[orig_idx] = tokens

        return results

    def _word_to_token(self, word, idx: int) -> AnalyzedToken:
        """Convert stanza word to AnalyzedToken."""
        # Parse features
        features = {}
        if word.feats:
            for feat in word.feats.split("|"):
                if "=" in feat:
                    k, v = feat.split("=", 1)
                    features[k] = v

        # Dependency info
        head_idx = None
        dep_rel = None
        if self.use_depparse:
            if hasattr(word, "head") and word.head is not None and word.head > 0:
                head_idx = word.head - 1  # Convert 1-indexed to 0-indexed
            if hasattr(word, "deprel") and word.deprel is not None:
                dep_rel = word.deprel

        # Get pymorphy parse for inflection: the parse most consistent with
        # stanza's own POS/Case/Number/Gender/VerbForm (audit fix M1/C1) —
        # see _select_pymorphy_parse for why an unconstrained lemma match
        # silently picks the wrong paradigm cell.
        parses = self.morph.parse(word.text)
        pymorphy_parse = _select_pymorphy_parse(parses, word.lemma, word.upos, features)

        return AnalyzedToken(
            text=word.text,
            lemma=word.lemma,
            pos=word.upos,
            features=features,
            idx=idx,
            dep_rel=dep_rel,
            head_idx=head_idx,
            extra={"pymorphy_parse": pymorphy_parse},
        )
