"""French verb-ending homophony errors (PoC flagship handler).

French's flagship native spelling error: several verb-form endings are
pronounced identically but spelled differently, so writers who compose by
ear (rather than by grammatical analysis) swap them. This handler corrupts
1st-group (``-er``) verbs along three homophonous axes, per
``docs/research/FRENCH_DESIGN.md`` section 5.2 and
``docs/research/FRENCH_POC_WORKFLOW.md``:

- ``inf_to_participle``: infinitive (``manger``) written as past participle
  (``mangé``) in an infinitive slot (governed by a modal verb or a
  preposition such as ``pour``/``de``/``à``).
- ``participle_to_inf``: past participle (``mangé``/``mangée``/``mangés``/
  ``mangées``) written as infinitive (``manger``) after an auxiliary
  (``avoir``/``être``).
- ``fut_cond_1sg``: 1st-person-singular future (``-ai``) written as
  conditional (``-ais``), or vice versa.

No inflection engine is involved (French R1 morph-parse refactor is
deferred): every rewrite is a plain string-ending swap, gated purely by UD
features/deprels and a data-driven whitelist
(``src/synterr/data/french/verb_ending_slots.json``) that restricts
corruption to 1st-group verbs for which the target endings are *actually*
attested homophones (share a Lexique ``phon`` cluster) - not just verbs that
happen to end in ``-er``. Some ``-er`` verbs (e.g. ``aider``) do not have an
inf/participle homophone pair (``ede`` vs ``Ede``), so the whitelist check is
per-subtype, not just per-lemma.

Per the project's ``can_apply`` precision principle: when the governing
context is ambiguous (no modal/ADP found for an infinitive, no aux found for
a participle, lemma missing from the whitelist, or the surface text does not
actually carry the expected ending) ``can_apply`` returns False rather than
guessing.
"""

from __future__ import annotations

import json
import random as random_module
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from synterr.core.protocol import AnalyzedToken, ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random


# --- Data loading -----------------------------------------------------------


def _data_path() -> Path:
    """Path to ``src/synterr/data/french/verb_ending_slots.json``.

    ``data/french`` has no ``__init__.py`` (not an importable package, unlike
    ``data/russian``), so this always resolves via the on-disk layout:
    ``languages/french/errors/verb_endings.py`` -> up to ``synterr/`` -> down
    into ``data/french``.
    """
    return Path(__file__).parent.parent.parent.parent / "data" / "french" / "verb_ending_slots.json"


@lru_cache(maxsize=1)
def _load_verb_slots() -> dict[str, Any]:
    """Load the 1st-group verb ending-cluster whitelist (cached).

    Returns an empty dict (handler becomes inert, never `{}`-KeyErrors) if
    the data file is missing rather than raising - consistent with how
    Russian resource loaders degrade (see
    ``languages/russian/resources.py:get_paronyms``).
    """
    path = _data_path()
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("verbs", {})


def _clusters_share_slots(lemma: str, slot_a: str, slot_b: str) -> bool:
    """True iff ``lemma`` has a phonemic cluster containing both slots.

    This is the actual homophony evidence: two forms only sound identical
    (and are thus a plausible ear-driven confusion) when Lexique grouped
    them under the same ``phon`` value, i.e. the same cluster's ``slots``
    list contains both.
    """
    entry = _load_verb_slots().get(lemma)
    if entry is None:
        return False
    for cluster in entry.get("clusters", []):
        slots = cluster.get("slots", [])
        if slot_a in slots and slot_b in slots:
            return True
    return False


# --- Capitalization (self-contained; no shared French inflector exists yet) -


def _match_capitalization(original: str, new: str) -> str:
    """Match the capitalization pattern of ``original`` onto ``new``.

    Mirrors ``languages.russian.inflector.match_capitalization`` (not
    imported - this handler owns exactly two files and no shared French
    inflector module exists yet per FRENCH_DESIGN.md section 4).
    """
    if not original or not new:
        return new
    if original.isupper() and len(original) > 1:
        return new.upper()
    if original[0].isupper():
        return new[0].upper() + new[1:] if len(new) > 1 else new.upper()
    return new


# --- String rewrites ---------------------------------------------------------


def _rewrite_inf_to_participle(word: str) -> str | None:
    """``manger`` -> ``mangé`` (drop ``-er``, append ``-é``)."""
    lower = word.lower()
    if not lower.endswith("er") or len(lower) <= 2:
        return None
    corrupted_lower = lower[:-2] + "é"
    return _match_capitalization(word, corrupted_lower)


def _rewrite_participle_to_inf(word: str) -> str | None:
    """``mangé``/``mangée``/``mangés``/``mangées`` -> ``manger``.

    Longest suffix checked first so ``-ées`` isn't mistaken for ``-és``.
    """
    lower = word.lower()
    for suffix in ("ées", "ée", "és", "é"):
        if lower.endswith(suffix):
            stem = lower[: -len(suffix)]
            return _match_capitalization(word, stem + "er")
    return None


def _rewrite_fut_to_cond(word: str) -> str | None:
    """``mangerai`` -> ``mangerais`` (append ``-s``)."""
    lower = word.lower()
    if not lower.endswith("ai"):
        return None
    return _match_capitalization(word, lower + "s")


def _rewrite_cond_to_fut(word: str) -> str | None:
    """``mangerais`` -> ``mangerai`` (drop ``-s``)."""
    lower = word.lower()
    if not lower.endswith("ais"):
        return None
    return _match_capitalization(word, lower[:-1])


# --- Dep-tree gates -----------------------------------------------------------

# Deprels an infinitive bears when its head is the governing modal/control verb
# ("veut manger", "peut partir").
_MODAL_INFINITIVE_DEPRELS = {"xcomp", "ccomp"}

# Deprels an ADP bears when introducing an infinitive it depends on
# ("pour manger", "avant de partir", "sans parler").
_ADP_INFINITIVE_DEPRELS = {"mark", "case"}

# Deprels the aux bears when attaching to the participle it forms a compound
# tense with (French UD: the participle is usually the clausal head and the
# aux attaches to it, not the reverse).
_AUX_DEPRELS = {"aux", "aux:tense", "aux:pass"}

_COMPOUND_TENSE_AUX_LEMMAS = {"avoir", "être"}


def _token_at(tokens: Sequence[AnalyzedToken], idx: int | None) -> AnalyzedToken | None:
    if idx is None or idx < 0 or idx >= len(tokens):
        return None
    return tokens[idx]


def _infinitive_governor(
    tokens: Sequence[AnalyzedToken], idx: int
) -> AnalyzedToken | None:
    """Find the modal verb or ADP that licenses this token as an infinitive slot.

    Returns None (ambiguous / no evidence) rather than guessing - an
    infinitive with no textual evidence that it sits in a governed slot
    (e.g. a bare infinitive used as a nominal, "Manger est un plaisir") is
    not corrupted.
    """
    token = tokens[idx]

    head = _token_at(tokens, token.head_idx)
    if (
        head is not None
        and head.pos in {"VERB", "AUX"}
        and token.dep_rel in _MODAL_INFINITIVE_DEPRELS
    ):
        return head

    for other in tokens:
        if (
            other.head_idx == idx
            and other.pos == "ADP"
            and other.dep_rel in _ADP_INFINITIVE_DEPRELS
        ):
            return other

    return None


def _compound_tense_aux(
    tokens: Sequence[AnalyzedToken], idx: int
) -> AnalyzedToken | None:
    """Find the avoir/être auxiliary attached to this participle, if any."""
    for other in tokens:
        if (
            other.head_idx == idx
            and other.pos == "AUX"
            and other.dep_rel in _AUX_DEPRELS
            and other.lemma in _COMPOUND_TENSE_AUX_LEMMAS
        ):
            return other
    return None


# --- Subtype classification --------------------------------------------------


def _classify(tokens: Sequence[AnalyzedToken], idx: int) -> str | None:
    """Deterministically classify which subtype (if any) applies at ``idx``.

    Returns None whenever any gate is ambiguous - see module docstring.
    """
    token = tokens[idx]
    if token.pos != "VERB":
        return None

    lemma = token.lemma
    if not lemma or not lemma.endswith("er"):
        return None

    if token.has_feature("VerbForm", "Inf"):
        if _infinitive_governor(tokens, idx) is None:
            return None
        if not _clusters_share_slots(lemma, "inf", "participle"):
            return None
        return "inf_to_participle"

    if token.has_feature("VerbForm", "Part"):
        if _compound_tense_aux(tokens, idx) is None:
            return None
        if not _clusters_share_slots(lemma, "inf", "participle"):
            return None
        return "participle_to_inf"

    if token.get_feature("Person") == "1" and token.get_feature("Number") == "Sing":
        if not _clusters_share_slots(lemma, "fut_1s", "cond"):
            return None
        if token.has_feature("Mood", "Ind") and token.has_feature("Tense", "Fut"):
            return "fut_cond_1sg"
        if token.has_feature("Mood", "Cnd"):
            return "fut_cond_1sg"

    return None


def _surface_check(subtype: str, token: AnalyzedToken, text: str) -> bool:
    """Final surface-text guard: the rewrite must have real evidence in the
    actual token text, not just the UD features (parser/fixture noise)."""
    lower = text.lower()
    if subtype == "inf_to_participle":
        return lower.endswith("er") and len(lower) > 2
    if subtype == "participle_to_inf":
        return lower.endswith(("ée", "ées", "és", "é"))
    if subtype == "fut_cond_1sg":
        if token.has_feature("Tense", "Fut"):
            return lower.endswith("ai")
        return lower.endswith("ais")
    return False


# --- Handler ------------------------------------------------------------------


class VerbEndingHomophonyHandler:
    """Ending-swap errors on homophonous 1st-group (``-er``) verb forms.

    See module docstring for the three subtypes and their gates. Tagged
    SPELL (not MORPH): the corruption is a pure orthographic rewrite of a
    homophone, not a grammeme substitution requiring an inflection engine -
    per FRENCH_DESIGN.md section 5.2 ("Catach's logogrammique" framing).
    """

    name = "verb_ending_homophony"
    subtypes = ["inf_to_participle", "participle_to_inf", "fut_cond_1sg"]
    category = "SPELL"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if a verb-ending homophony error can be applied at ``idx``."""
        if idx < 0 or idx >= len(tokens):
            return False
        token = tokens[idx]
        subtype = _classify(tokens, idx)
        if subtype is None:
            return False
        return _surface_check(subtype, token, token.text)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply a verb-ending homophony error at ``idx``."""
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        subtype = _classify(tokens, idx)
        if subtype is None or not _surface_check(subtype, token, word):
            return None

        if subtype == "inf_to_participle":
            corrupted = _rewrite_inf_to_participle(word)
        elif subtype == "participle_to_inf":
            corrupted = _rewrite_participle_to_inf(word)
        else:  # fut_cond_1sg
            if token.has_feature("Tense", "Fut"):
                corrupted = _rewrite_fut_to_cond(word)
            else:
                corrupted = _rewrite_cond_to_fut(word)

        if corrupted is None or corrupted == word:
            return None

        sentence[idx] = corrupted
        modified.add(idx)

        return ErrorResult(
            error_type=subtype,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{word}",
        )
