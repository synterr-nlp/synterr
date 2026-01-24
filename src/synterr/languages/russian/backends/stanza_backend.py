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

if TYPE_CHECKING:
    from collections.abc import Sequence


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
                "tokenize,pos,lemma,depparse" if self.use_depparse else "tokenize,pos,lemma"
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

        # Get pymorphy parse for inflection
        parses = self.morph.parse(word.text)
        pymorphy_parse = None

        # Try to match by lemma first
        for p in parses:
            if p.normal_form == word.lemma:
                pymorphy_parse = p
                break

        if pymorphy_parse is None and parses:
            pymorphy_parse = parses[0]

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
