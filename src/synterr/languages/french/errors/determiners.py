"""French article-contraction error handler (PoC).

Implements ``article_contraction`` from the French PoC handler roster
(docs/research/FRENCH_POC_WORKFLOW.md, row #3; docs/research/FRENCH_DESIGN.md
§5.2). Three subtypes, each de-contracting a categorical préposition + article
défini fusion back into its two separate words — the canonical L2 "forgot to
contract" error:

    au_split   au  -> "à le"   (à + le,  masc. sg.)
    aux_split  aux -> "à les"  (à + les, plur., both genders)
    du_split   du  -> "de le"  (de + le, masc. sg.) — ONLY when unambiguously
               the contracted definite article, never the homographic
               partitive determiner ("il boit du café"); see the du gate below.

Gate data (expansions, BDL citations, the au/aux-are-unconditional-vs-
du-is-ambiguous distinction) lives in ``data/french/contractions.json``, not
hardcoded, so the linguistic facts stay separately auditable from the
syntactic gate.

Tokenizer reality (cross-checked against a real
``StanzaFrBackend(use_depparse=True)`` parse — see the ``tokens_au_contraction``
and ``tokens_du_contraction`` fixtures in
``tests/test_languages/test_french/conftest.py``): fr_sequoia always expands
"au"/"aux"/"du" as multi-word tokens into an ADP ("à"/"de") followed by a DET
("le"/"les"), both attached to the same head noun (``case`` / ``det``), and
``_word_to_token`` iterates the already-expanded ``sent.words``. So the
two-word spelling is already what sits in ``sentence``: ``apply()`` mutates
nothing. On clean input a matching ADP+DET pair can only come from a fused
form, so the handler only gates where that holds (the du gate) and reports
``original`` = the fused spelling (never in the token array), ``corrupted`` =
the two-word span. ``changes_length = True`` anyway, because the semantic
operation is a length change (one word → two); it keeps the handler in the
pipeline's single length-changing slot.

The ``du`` gate (per ``contractions.json``'s ``du`` entry and the BDL source
cited there): ``du`` is split only when its head is a NOUN whose dep_rel is in
the nmod/obl family (``la porte du garage``, ``le plat du jour``), and never
when the head is a verb's object or subject (obj/iobj/nsubj/csubj, incl.
``:pass``) — the signature of the homographic *partitive* determiner
(``boire du café``, ``avoir du courage``), which has no de+le paraphrase.
Definiteness itself is not checked; the deprel gate stands in for it, and any
ambiguity refuses (precision over recall).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# --- Data loading ------------------------------------------------------------


def _data_dir() -> Path:
    """``src/synterr/data/french``.

    ``data/french`` has no ``__init__.py`` (not an importable package, unlike
    ``data/russian``), so this always resolves via the on-disk layout:
    ``languages/french/errors/determiners.py`` -> up to ``synterr/`` -> down
    into ``data/french`` (same convention as ``elision.py``/``verb_endings.py``).
    """
    return Path(__file__).parent.parent.parent.parent / "data" / "french"


@lru_cache(maxsize=1)
def _load_contractions() -> dict[str, dict]:
    """Load ``contractions.json``, dropping the ``_meta`` key. Degrades to
    ``{}`` (handler becomes inert, never KeyErrors) if the data file is
    missing — consistent with how other French resource loaders degrade."""
    path = _data_dir() / "contractions.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


# --- Capitalization helper ---------------------------------------------------
#
# Duplicated (not imported) from
# synterr.languages.russian.inflector.match_capitalization: it is a pure,
# language-agnostic string utility, but importing across language packages
# would create an unwanted Russian<->French coupling ahead of the planned R1
# shared-module extraction (FRENCH_DESIGN.md §4). Same duplication already
# made in errors/elision.py and errors/homophony.py; kept semantically
# identical to those.


def _match_capitalization(original: str, new: str) -> str:
    """Match the capitalization pattern of ``original`` onto ``new``."""
    if not original or not new:
        return new
    if original.isupper() and len(original) > 1:
        return new.upper()
    if original[0].isupper():
        return new[0].upper() + new[1:] if len(new) > 1 else new.upper()
    return new


# --- du gate ------------------------------------------------------------------

# Head dep_rels that signal a genuine de+le (genitive/source-complement)
# reading — an nmod-family dependent of another noun, or an oblique argument
# introducing a source/location complement.
_DU_ALLOWED_HEAD_DEPRELS = ("nmod", "obl")

# Head dep_rels that signal the head noun is a verb's (in)direct object or
# subject — the partitive signature ("boire du café", "du pain reste"). Any
# of these on the head refuses the split outright, even if it happens to
# also match one of the allowed prefixes above (defence in depth).
_DU_PARTITIVE_HEAD_DEPRELS = frozenset(
    {"obj", "iobj", "nsubj", "nsubj:pass", "csubj", "csubj:pass"}
)


class ArticleContractionHandler:
    """De-contract categorical à/de + le/les fusions (``au``/``aux``/``du``)
    back into their two separate words. See module docstring for the full
    mechanic, the tokenizer reality it is built against, and the du gate.
    """

    name = "article_contraction"
    subtypes = ["au_split", "aux_split", "du_split"]
    category = "MORPH"
    changes_length = True

    # -- gate ---------------------------------------------------------------

    def _classify(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[str, str] | None:
        """Return ``(subtype, fused_lowercase)`` if ``idx`` is the ADP half
        of a splittable ADP+DET contraction pair, else ``None``."""
        if idx < 0 or idx + 1 >= len(tokens):
            return None

        adp = tokens[idx]
        det = tokens[idx + 1]

        if adp.pos != "ADP" or det.pos != "DET":
            return None
        if adp.dep_rel != "case" or det.dep_rel != "det":
            return None
        if adp.head_idx is None or det.head_idx is None:
            return None
        if adp.head_idx != det.head_idx:
            return None

        adp_text = (adp.text or "").lower()
        det_text = (det.text or "").lower()

        for subtype_key, entry in _load_contractions().items():
            expands_to = entry.get("expands_to")
            if not expands_to or len(expands_to) != 2:
                continue
            want_adp, want_det = expands_to[0].lower(), expands_to[1].lower()
            if adp_text != want_adp or det_text != want_det:
                continue
            if subtype_key == "du" and not self._du_gate_ok(tokens, adp.head_idx):
                return None
            return (f"{subtype_key}_split", subtype_key)

        return None

    def _du_gate_ok(self, tokens: Sequence[AnalyzedToken], head_idx: int) -> bool:
        """``du`` may only split when its head is a NOUN whose dep_rel is in
        the nmod/obl family — never a verb's (in)direct object or subject
        (the partitive signature). Any ambiguity refuses."""
        if head_idx < 0 or head_idx >= len(tokens):
            return False
        head = tokens[head_idx]
        if head.pos != "NOUN":
            return False
        if head.dep_rel is None:
            return False
        if head.dep_rel in _DU_PARTITIVE_HEAD_DEPRELS:
            return False
        return any(
            head.dep_rel == family or head.dep_rel.startswith(family + ":")
            for family in _DU_ALLOWED_HEAD_DEPRELS
        )

    # -- protocol -------------------------------------------------------------

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._classify(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        classification = self._classify(tokens, idx)
        if classification is None:
            return None
        if idx in modified or (idx + 1) in modified:
            return None

        subtype, fused_lower = classification

        # Defence in depth: sentence should already mirror tokens' text at
        # these two positions (see module docstring — no prior handler has
        # any reason to touch an ADP/DET contraction pair). If some earlier
        # corruption already changed either slot, refuse rather than build
        # an ErrorResult around text that no longer matches what we gated on.
        if (
            sentence[idx] != tokens[idx].text
            or sentence[idx + 1] != tokens[idx + 1].text
        ):
            return None

        fused = _match_capitalization(tokens[idx].text, fused_lower)
        corrupted = f"{sentence[idx]} {sentence[idx + 1]}"

        return ErrorResult(
            error_type=f"{self.name}_{subtype}",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 2,
            original=fused,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{fused}",
        )
