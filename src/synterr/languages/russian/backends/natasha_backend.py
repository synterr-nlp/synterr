"""Natasha/Slovnet backend for Russian language analysis.

Natasha is a lightweight Russian NLP library using Slovnet neural models.
Fastest option with good accuracy, optimized for Russian.

Accuracy:
    - POS: ~98.2%
    - Morph features: ~98%
    - Dependency: 93.6% LAS

Speed: ~500 sentences/second (CPU)
Model size: ~30 MB total

Note: Lemmatization uses pymorphy3, not Slovnet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken

if TYPE_CHECKING:
    from collections.abc import Sequence


class NatashaBackend:
    """Natasha/Slovnet-based analyzer for Russian.

    Uses Natasha library with Slovnet models for fast, accurate Russian NLP.
    Provides POS tagging, morphological analysis, and dependency parsing.
    Lemmatization via pymorphy3.
    """

    name = "natasha"
    supports_depparse = True

    def __init__(self, use_depparse: bool = False, use_gpu: bool = True) -> None:
        """Initialize Natasha backend.

        Args:
            use_depparse: Enable dependency parsing
            use_gpu: Ignored (Natasha doesn't use GPU)
        """
        self.use_depparse = use_depparse
        self._segmenter = None
        self._morph_tagger = None
        self._syntax_parser = None
        self._morph = None

    @property
    def segmenter(self):
        """Lazy-initialize tokenizer."""
        if self._segmenter is None:
            from natasha import Segmenter

            self._segmenter = Segmenter()
        return self._segmenter

    @property
    def morph_tagger(self):
        """Lazy-initialize morphological tagger."""
        if self._morph_tagger is None:
            from natasha import MorphVocab, NewsEmbedding, NewsMorphTagger

            emb = NewsEmbedding()
            self._morph_vocab = MorphVocab()
            self._morph_tagger = NewsMorphTagger(emb)
        return self._morph_tagger

    @property
    def syntax_parser(self):
        """Lazy-initialize syntax parser."""
        if self._syntax_parser is None and self.use_depparse:
            from natasha import NewsEmbedding, NewsSyntaxParser

            emb = NewsEmbedding()
            self._syntax_parser = NewsSyntaxParser(emb)
        return self._syntax_parser

    @property
    def morph(self):
        """Lazy-initialize pymorphy3 for inflection and lemmatization."""
        if self._morph is None:
            import pymorphy3

            self._morph = pymorphy3.MorphAnalyzer()
        return self._morph

    def analyze(self, text: str) -> list[AnalyzedToken]:
        """Analyze a single sentence."""
        from natasha import Doc

        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)

        if self.use_depparse and self.syntax_parser:
            doc.parse_syntax(self.syntax_parser)

        tokens = []
        for i, token in enumerate(doc.tokens):
            analyzed = self._token_to_analyzed(token, i)
            tokens.append(analyzed)

        return tokens

    def analyze_batch(self, texts: Sequence[str]) -> list[list[AnalyzedToken]]:
        """Analyze multiple sentences."""
        # Natasha doesn't have native batching, process one by one
        return [self.analyze(text) for text in texts]

    def _token_to_analyzed(self, token, idx: int) -> AnalyzedToken:
        """Convert Natasha token to AnalyzedToken."""
        # Parse features from Natasha format
        features = {}
        pos = "X"

        if hasattr(token, "pos") and token.pos:
            pos = token.pos

        if hasattr(token, "feats") and token.feats:
            # Natasha feats is already a dict
            features = dict(token.feats) if token.feats else {}

        # Dependency info
        head_idx = None
        dep_rel = None
        if self.use_depparse:
            if hasattr(token, "head_id") and token.head_id:
                # Natasha uses string IDs, need to map
                head_idx = self._get_head_index(token)
            if hasattr(token, "rel") and token.rel:
                dep_rel = token.rel

        # Get pymorphy parse for lemma and inflection
        parses = self.morph.parse(token.text)
        pymorphy_parse = parses[0] if parses else None
        lemma = pymorphy_parse.normal_form if pymorphy_parse else token.text

        return AnalyzedToken(
            text=token.text,
            lemma=lemma,
            pos=pos,
            features=features,
            idx=idx,
            dep_rel=dep_rel,
            head_idx=head_idx,
            extra={"pymorphy_parse": pymorphy_parse},
        )

    def _get_head_index(self, token) -> int | None:
        """Get head token index from Natasha token."""
        # This is a simplified implementation
        # In practice, you'd need to track token IDs
        if hasattr(token, "head_id"):
            try:
                # Natasha uses 1-based string IDs like "1_1"
                if token.head_id and "_" in token.head_id:
                    return int(token.head_id.split("_")[1]) - 1
            except (ValueError, IndexError):
                pass
        return None
