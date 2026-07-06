"""Stanza backend for French language analysis (PoC).

Stanza provides UD analysis using the ``fr_sequoia`` package, trained on the
Sequoia treebank. Per FRENCH_DESIGN.md section 3, ``fr_sequoia`` was chosen
over spaCy's ``fr_dep_news_trf`` for its lemma accuracy (dictionary key for
future resource lookups), even though this PoC backend does not yet build a
morphological parse object.

Unlike the Russian stanza backend, this backend leaves ``AnalyzedToken.extra``
empty (``{}``). The French PoC handlers (docs/research/FRENCH_POC_WORKFLOW.md)
are string rewrites gated purely by UD POS/lemma/features/deprels - none of
them read an inflection-engine parse - so the R1 core refactor
(``pymorphy_parse`` -> ``morph_parse`` protocol) and its French analog
(Lefff/verbecc-backed ``FrenchParse``) stay deferred to phase 1 proper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken

if TYPE_CHECKING:
    from collections.abc import Sequence


class StanzaFrBackend:
    """Stanza-based analyzer for French.

    Uses Stanford NLP stanza library with the French `sequoia` package.
    Provides POS tagging, morphological features, lemmatization, and
    optional dependency parsing. No inflection engine is attached (PoC).
    """

    name = "stanza"
    supports_depparse = True

    def __init__(self, use_depparse: bool = False, use_gpu: bool = True) -> None:
        """Initialize Stanza French backend.

        Args:
            use_depparse: Enable dependency parsing
            use_gpu: Use GPU acceleration
        """
        self.use_depparse = use_depparse
        self.use_gpu = use_gpu
        self._nlp = None

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
                "fr",
                package="sequoia",
                processors=processors,
                verbose=False,
                use_gpu=self.use_gpu,
            )
        return self._nlp

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
        """Convert stanza word to AnalyzedToken.

        No inflection engine is attached in the PoC - ``extra`` is always
        ``{}`` (see module docstring).
        """
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

        return AnalyzedToken(
            text=word.text,
            lemma=word.lemma,
            pos=word.upos,
            features=features,
            idx=idx,
            dep_rel=dep_rel,
            head_idx=head_idx,
            extra={},
        )
