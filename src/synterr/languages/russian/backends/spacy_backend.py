"""spaCy backend for Russian language analysis.

spaCy provides balanced speed and accuracy with good dependency parsing.
Note: spaCy's Russian lemmatizer is broken, we use pymorphy3 instead.

Accuracy (ru_core_news_lg):
    - POS: 98.93%
    - Morph features: 97.49%
    - Dependency: 95.12% LAS
    - Lemma: BROKEN (0%) - we use pymorphy3

Speed: ~500 sentences/second (CPU)
Model size: ~500 MB (lg model)

Available models:
    - ru_core_news_sm: Small, fastest
    - ru_core_news_md: Medium, balanced
    - ru_core_news_lg: Large, best accuracy
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken

if TYPE_CHECKING:
    from collections.abc import Sequence


class SpacyBackend:
    """spaCy-based analyzer for Russian.

    Uses spaCy with Russian models (ru_core_news_*).
    Lemmatization via pymorphy3 since spaCy's Russian lemmatizer is broken.
    """

    name = "spacy"
    supports_depparse = True

    def __init__(
        self,
        use_depparse: bool = False,
        use_gpu: bool = True,
        model: str = "ru_core_news_md",
    ) -> None:
        """Initialize spaCy backend.

        Args:
            use_depparse: Enable dependency parsing
            use_gpu: Use GPU acceleration
            model: spaCy model name (ru_core_news_sm/md/lg)
        """
        self.use_depparse = use_depparse
        self.use_gpu = use_gpu
        self.model_name = model
        self._nlp = None
        self._morph = None

    @property
    def nlp(self):
        """Lazy-initialize spaCy pipeline."""
        if self._nlp is None:
            import spacy

            # Try to use GPU
            if self.use_gpu:
                import contextlib

                with contextlib.suppress(Exception):
                    spacy.prefer_gpu()

            # Load model
            try:
                self._nlp = spacy.load(self.model_name)
            except OSError as e:
                raise ImportError(
                    f"spaCy model '{self.model_name}' not found. "
                    f"Install with: python -m spacy download {self.model_name}"
                ) from e

            # Disable components we don't need
            disable = ["ner"]
            if not self.use_depparse:
                disable.append("parser")

            for component in disable:
                if component in self._nlp.pipe_names:
                    self._nlp.disable_pipe(component)

        return self._nlp

    @property
    def morph(self):
        """Lazy-initialize pymorphy3 for lemmatization."""
        if self._morph is None:
            import pymorphy3

            self._morph = pymorphy3.MorphAnalyzer()
        return self._morph

    def analyze(self, text: str) -> list[AnalyzedToken]:
        """Analyze a single sentence."""
        doc = self.nlp(text)
        return [self._token_to_analyzed(token, i) for i, token in enumerate(doc)]

    def analyze_batch(self, texts: Sequence[str]) -> list[list[AnalyzedToken]]:
        """Analyze multiple sentences with spaCy's pipe."""
        results = []
        for doc in self.nlp.pipe(texts, batch_size=50):
            tokens = [self._token_to_analyzed(token, i) for i, token in enumerate(doc)]
            results.append(tokens)
        return results

    def _token_to_analyzed(self, token, idx: int) -> AnalyzedToken:
        """Convert spaCy token to AnalyzedToken."""
        # Parse morphological features
        features = {}
        if token.morph:
            for feat in token.morph:
                if "=" in feat:
                    k, v = feat.split("=", 1)
                    features[k] = v

        # Dependency info
        head_idx = None
        dep_rel = None
        if self.use_depparse:
            if token.head != token:  # Not root
                head_idx = token.head.i
            dep_rel = token.dep_

        # Get pymorphy parse for lemma (spaCy's is broken) and inflection
        parses = self.morph.parse(token.text)
        pymorphy_parse = parses[0] if parses else None
        lemma = pymorphy_parse.normal_form if pymorphy_parse else token.text

        return AnalyzedToken(
            text=token.text,
            lemma=lemma,
            pos=token.pos_,
            features=features,
            idx=idx,
            dep_rel=dep_rel,
            head_idx=head_idx,
            extra={"pymorphy_parse": pymorphy_parse},
        )
