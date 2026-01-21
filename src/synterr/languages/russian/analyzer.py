"""Russian language analyzer using stanza and pymorphy3."""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken

if TYPE_CHECKING:
    from collections.abc import Sequence


class RussianAnalyzer:
    """Russian text analyzer combining stanza (contextual) and pymorphy3 (inflection).

    Uses stanza for contextual morphological analysis (POS, lemma, features, depparse)
    and pymorphy3 for inflection capabilities.
    """

    def __init__(self, use_depparse: bool = False, use_gpu: bool = True) -> None:
        """Initialize Russian analyzer.

        Args:
            use_depparse: Enable dependency parsing (~40% slower)
            use_gpu: Use GPU acceleration for stanza
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
        """Lazy-initialize pymorphy3 analyzer."""
        if self._morph is None:
            import pymorphy3

            self._morph = pymorphy3.MorphAnalyzer()
        return self._morph

    def analyze(self, text: str) -> list[AnalyzedToken]:
        """Analyze a single sentence.

        Args:
            text: Input sentence text

        Returns:
            List of analyzed tokens
        """
        doc = self.nlp(text)
        tokens = []

        for sent in doc.sentences:
            for word in sent.words:
                token = self._word_to_token(word, len(tokens))
                tokens.append(token)

        return tokens

    def analyze_batch(self, texts: Sequence[str]) -> list[list[AnalyzedToken]]:
        """Analyze multiple sentences (batched for efficiency).

        Batching gives ~7x speedup over processing one-at-a-time.

        Args:
            texts: List of sentence texts

        Returns:
            List of token lists, one per sentence
        """
        if not texts:
            return []

        # Join sentences with double newline (stanza sentence boundary)
        batch_text = "\n\n".join(texts)

        # Process entire batch at once
        doc = self.nlp(batch_text)

        # Map stanza sentences back to input sentences
        results = []
        stanza_sent_idx = 0

        for orig_text in texts:
            if stanza_sent_idx >= len(doc.sentences):
                # Stanza produced fewer sentences than expected
                tokens = self._fallback_analyze(orig_text)
            else:
                stanza_sent = doc.sentences[stanza_sent_idx]
                tokens = []

                for i, word in enumerate(stanza_sent.words):
                    token = self._word_to_token(word, i)
                    tokens.append(token)

                stanza_sent_idx += 1

            results.append(tokens)

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

        # Dependency info (head is 1-indexed in stanza, convert to 0-indexed)
        head_idx = None
        dep_rel = None
        if self.use_depparse:
            if hasattr(word, "head") and word.head is not None and word.head > 0:
                head_idx = word.head - 1
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

        # Fallback to first parse
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

    def _fallback_analyze(self, text: str) -> list[AnalyzedToken]:
        """Fallback analysis using pymorphy3 when stanza fails."""
        from razdel import tokenize

        # Map pymorphy POS to Universal POS
        pos_map = {
            "NOUN": "NOUN",
            "VERB": "VERB",
            "INFN": "VERB",
            "ADJF": "ADJ",
            "ADJS": "ADJ",
            "ADVB": "ADV",
            "NPRO": "PRON",
            "NUMR": "NUM",
            "PREP": "ADP",
            "CONJ": "CCONJ",
            "PRCL": "PART",
            "INTJ": "INTJ",
        }

        tokens = []
        for i, tok in enumerate(tokenize(text)):
            word = tok.text
            parses = self.morph.parse(word)

            if parses:
                parse = parses[0]
                pos = pos_map.get(parse.tag.POS, "X")
                lemma = parse.normal_form
            else:
                pos = "X"
                lemma = word

            token = AnalyzedToken(
                text=word,
                lemma=lemma,
                pos=pos,
                features={},
                idx=i,
                extra={"pymorphy_parse": parses[0] if parses else None},
            )
            tokens.append(token)

        return tokens
