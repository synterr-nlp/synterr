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

Tokenizer reality this handler is built against (cross-checked against a real
``StanzaFrBackend(use_depparse=True)`` parse — see
``tests/test_languages/test_french/conftest.py``'s ``tokens_au_contraction``
and ``tokens_du_contraction`` fixtures and their docstrings):

- fr_sequoia treats "au"/"aux"/"du" as multi-word tokens (MWT) and *always*
  expands them into two syntactic words before any handler ever sees them:
  an ADP ("à"/"de") immediately followed by a DET ("le"/"les"), both attached
  to the same head noun (``dep_rel="case"`` / ``dep_rel="det"``,
  matching ``head_idx``). This is true regardless of whether the underlying
  clean sentence spelled the word "au" (correct) — the analyzed token stream
  can never contain a literal fused "au" token, because ``_word_to_token``
  (``backends/stanza_fr.py``) iterates ``sent.words``, which is already
  MWT-expanded.
- Because ``sentence`` is built as ``[t.text for t in tokens]``
  (``core/pipeline.py``), this means the *un-contracted* two-word spelling —
  "à le" / "à les" / "de le" — is already what sits in ``sentence`` at these
  two adjacent positions before this handler ever runs. There is no fused
  "au" token anywhere in the mutable token array for this handler to split;
  the split has, in effect, already happened upstream in tokenization.
- Consequently ``apply()`` does not insert or delete anything: given a clean
  corpus sentence (the only kind this pipeline corrupts), a matched
  ADP+DET pair at this gate is *by construction* the analysis of a genuine
  "au"/"aux"/"du" in the source text, so the handler's job reduces to (a)
  precisely gating *where* that is true (the du gate is the whole point —
  see below) and (b) reporting the correct/corrupted pair as an
  ``ErrorResult`` — ``original`` reconstructs the fused spelling (never
  materialized in the token array), ``corrupted`` is the two-word span
  already present in ``sentence``. This mirrors ``elision_apostrophe``'s
  documented tokenizer quirks (``errors/elision.py``) and is the same kind of
  "known PoC cut corner" as the rest of the French scaffold — it is not
  introduced by this handler, only worked around within it.
- ``changes_length = True`` is declared at the class level per the
  ``ErrorHandler`` protocol (one bool per *handler*), matching the same
  reasoning ``ElisionApostropheHandler`` documents for its own split/merge
  subtypes: the *semantic* operation ("au" is one word, "à le" is two) is a
  length change even though this particular tokenizer already presents the
  span pre-split, so no array mutation is actually required to realize it.
  Declaring it True keeps the handler correctly deferred to the single
  per-sentence length-changing slot rather than competing on index-stability
  assumptions with in-place handlers.

The ``du`` gate (per ``contractions.json``'s ``du`` entry and the BDL source
cited there): ``du`` is only split when it is unambiguously the contracted
definite article — i.e. it introduces an ``nmod``/``obl``-family dependent of
a definite, uniquely-referring NOUN (``la porte du garage``, ``le plat du
jour``). It must never be split when it is the homographic *partitive*
determiner marking an indeterminate quantity as a verb's (in)direct object
(``boire du café``, ``avoir du courage``) — that reading has no de+le
paraphrase at all. Per this project's ``can_apply`` precision principle
("a corruption that lands accidentally correct is worse than no corruption"),
the gate requires the head to be POS=NOUN with a dep_rel in the nmod/obl
family, and explicitly refuses obj/iobj/subject dep_rels (the partitive
signature) rather than trying to guess semantics from features alone.
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
        """``du`` may only split when its head is a definite/unique-referent
        NOUN reached via an nmod/obl dependent — never a verb's (in)direct
        object or subject (the partitive signature). Conservative by
        design: any ambiguity refuses, per this project's ``can_apply``
        precision principle."""
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
