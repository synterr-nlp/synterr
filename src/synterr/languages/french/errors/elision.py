"""French elision-apostrophe error handler (PoC).

Two subtypes on one handler (see FRENCH_DESIGN.md section 5.2, row
``elision_apostrophe``, and FRENCH_POC_WORKFLOW.md row 4 — this PoC scopes
the row down to two subtypes, ``elision_omit`` and ``euphonic_t_drop``):

- ``elision_omit``: un-elides a clitic/article/conjunction that fr_sequoia
  tokenizes as its own token ending in an apostrophe — ``l'``/``j'``/``qu'``/
  ... — restoring the full form as a separate word:
  ``l'arbre`` → "le arbre", ``qu'il`` → "que il", ``j'ai`` → "je ai".
  Categorical string rewrite gated on a closed elision lexicon
  (``data/french/elision.json``); no inflection engine is involved (per the
  PoC's "string rewrites gated by UD features/deprels" scope trick).
- ``euphonic_t_drop``: deletes the ``-t-`` euphonique token inserted between
  a vowel-final verb and an inverted 3rd-person subject pronoun
  (il/elle/on): ``aime-t-il`` → "aime il". Gated on
  ``data/french/euphonic_t.json``'s rule (verb form ends in -e/-a).

Tokenizer verification (against ``tests/test_languages/test_french/conftest.py``
fixtures, themselves cross-checked against a real
``StanzaFrBackend(use_depparse=True)`` parse — see FRENCH_POC_WORKFLOW.md):

- Elided clitics are NOT fused with the following word: fr_sequoia tokenizes
  "l'arbre" as two tokens, ``l'`` and ``arbre`` (see ``tokens_elided_l``,
  ``tokens_elided_qu``). ``elision_omit`` therefore never needs to insert or
  delete a token — it is always an in-place ``$REPLACE`` on the elided token
  alone. This subtype, on its own, does not change token count.
- The euphonic ``-t-`` of "-t-il" inversions is its own token (``-t``),
  separate from the following pronoun token (``-il``) — see
  ``tokens_t_il_inversion``. ``euphonic_t_drop`` deletes that whole token, so
  it IS length-changing.
- Because ``ErrorHandler.changes_length`` is one bool per *handler*, not per
  subtype (see ``FunctionSpellingHandler`` in the Russian tree for the same
  pattern with split/merge subtypes that don't all change length), this
  handler declares ``changes_length = True`` overall: the pipeline defers it
  to the single length-changing slot per sentence, which is always safe
  (applying an in-place ``elision_omit`` replace after other handlers
  corrupts no index — only ``euphonic_t_drop`` actually shifts indices). The
  cost is that ``elision_omit`` competes with ``euphonic_t_drop`` (and any
  other length-changing handler) for that one per-sentence slot; acceptable
  for a PoC.
- Joined-sentence rendering quirk (pre-existing, not introduced here): the
  pipeline reconstructs surface text via ``" ".join(sentence)``
  (``core/pipeline.py``), so a hyphen-leading token like ``-il`` renders with
  a literal space before its hyphen (e.g. "Aime -il ...") rather than true
  French "Aime-il". This is a property of how fr_sequoia's hyphenated
  inversion tail is tokenized generally, not specific to this handler.
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
    ``languages/french/errors/elision.py`` -> up to ``synterr/`` -> down into
    ``data/french`` (same convention as ``verb_endings.py``).
    """
    return Path(__file__).parent.parent.parent.parent / "data" / "french"


@lru_cache(maxsize=1)
def _load_elision() -> dict[str, dict]:
    """Load ``elision.json``, dropping the ``_meta`` key. Degrades to ``{}``
    (handler becomes inert, never KeyErrors) if the data file is missing —
    consistent with how Russian resource loaders degrade."""
    path = _data_dir() / "elision.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def _load_h_aspire() -> frozenset[str]:
    """Lowercased h-aspiré headword set. h-aspiré words must never be
    treated as elision sites (see module docstring)."""
    path = _data_dir() / "h_aspire.json"
    if not path.exists():
        return frozenset()
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return frozenset(k.lower() for k in data if not k.startswith("_"))


@lru_cache(maxsize=1)
def _load_euphonic_t() -> dict[str, Any]:
    """Load ``euphonic_t.json``'s ``trigger`` rule block."""
    path = _data_dir() / "euphonic_t.json"
    if not path.exists():
        return {"trigger": {"pronouns": [], "verb_ending_triggers": []}}
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


@lru_cache(maxsize=1)
def _elided_form_index() -> dict[str, list[str]]:
    """Map elided surface form (with apostrophe, e.g. ``"l'"``) to the list
    of full forms that can produce it (e.g. ``["le", "la"]``). Several full
    forms share an elided form (``l'`` <- le/la; ``s'`` <- se/si);
    disambiguation happens in ``_resolve_full_form`` via POS/features, never
    by arbitrary dict order here."""
    index: dict[str, list[str]] = {}
    for full_form, entry in _load_elision().items():
        elided = entry.get("elided_form")
        if not elided:
            continue
        index.setdefault(elided, []).append(full_form)
    return index


# --- Small local helpers (no shared French inflector module exists yet;
# see FRENCH_DESIGN.md section 4 — deferred until the R1 refactor lands) ----


def _strip_apostrophe(text: str) -> str | None:
    """Return the elided-form lookup key (lowercased, incl. apostrophe) if
    ``text`` ends in a straight or typographic apostrophe, else ``None``."""
    if len(text) < 2:
        return None
    if text[-1] not in ("'", "’"):
        return None
    return text[:-1].lower() + "'"


def _match_capitalization(original: str, new: str) -> str:
    """Match ``original``'s capitalization pattern onto ``new``.

    French-local re-implementation of the Russian inflector helper of the
    same name (``languages.russian.inflector.match_capitalization``) — not
    imported from there since French must not depend on the Russian
    language package. Diverges from the Russian version in one respect:
    capitalization is judged over ``original``'s *alphabetic* characters
    only, not ``len(original)``. Elided tokens carry a trailing apostrophe
    (``"S'"``, ``"L'"``), and Python's ``str.isupper()`` ignores non-cased
    characters — ``"S'".isupper()`` is ``True`` even though there is only one
    actual letter, which would otherwise wrongly route a single capital
    letter through the all-caps branch (producing "SI" instead of "Si").
    """
    if not original or not new:
        return new
    letters = [c for c in original if c.isalpha()]
    if len(letters) > 1 and all(c.isupper() for c in letters):
        return new.upper()
    if letters and letters[0].isupper():
        return new[0].upper() + new[1:] if len(new) > 1 else new.upper()
    return new


class ElisionApostropheHandler:
    """Un-elide clitics/articles (``elision_omit``) and drop the ``-t-``
    euphonique of pronoun inversions (``euphonic_t_drop``). See module
    docstring for the full mechanic and the tokenizer verification behind
    ``changes_length``.
    """

    name = "elision_apostrophe"
    subtypes = ["elision_omit", "euphonic_t_drop"]
    category = "SPELL"
    changes_length = True

    # -- elision_omit ---------------------------------------------------

    def _resolve_full_form(
        self, tok: AnalyzedToken, next_tok: AnalyzedToken | None
    ) -> str | None:
        """Return the correct full form for an elided token, or ``None`` if
        the gate is ambiguous (le/la, se/si) and cannot be resolved from
        available features — conservative, per the ``can_apply`` precision
        principle (a wrong guess here would silently pick the wrong
        article/pronoun, a worse outcome than skipping the site)."""
        key = _strip_apostrophe(tok.text)
        if key is None:
            return None
        candidates = _elided_form_index().get(key)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        candidate_set = set(candidates)

        if candidate_set == {"le", "la"}:
            # le/la (article or 3rd-person object clitic) both elide to l'.
            # Disambiguate via Gender: the DET's own Gender feature if
            # present, else (fr_sequoia's article tokens sometimes lack it,
            # see tokens_elided_l) the following NOUN/ADJ/PROPN it agrees
            # with. Clitic-pronoun uses before a verb (no nominal head
            # nearby) stay unresolved — out of scope for this PoC.
            gender = tok.get_feature("Gender")
            if gender is None and next_tok is not None and next_tok.pos in (
                "NOUN",
                "ADJ",
                "PROPN",
            ):
                gender = next_tok.get_feature("Gender")
            if gender == "Masc":
                return "le"
            if gender == "Fem":
                return "la"
            return None

        if candidate_set == {"se", "si"}:
            # se (reflexive clitic, PRON before a verb) vs si (conjunction,
            # SCONJ) — elision.json restricts si's elision to s'il/s'ils.
            if tok.pos == "SCONJ":
                if next_tok is None:
                    return None
                if next_tok.text.lower().lstrip("-") in ("il", "ils"):
                    return "si"
                return None
            if tok.pos == "PRON":
                return "se"
            return None

        # Any other ambiguous cluster this lexicon might grow into later —
        # no disambiguation rule written yet, refuse rather than guess.
        return None

    def _can_apply_elision_omit(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        tok = tokens[idx]
        key = _strip_apostrophe(tok.text)
        if key is None:
            return False
        if key not in _elided_form_index():
            return False
        if idx + 1 >= len(tokens):
            return False
        next_tok = tokens[idx + 1]
        if next_tok.pos == "PUNCT":
            return False
        # Defense in depth: on clean input this should never occur (elision
        # would be ungrammatical before an h-aspiré word), but never trust
        # it silently — h-aspiré words must never be counted as elision
        # sites.
        if next_tok.text.lower() in _load_h_aspire():
            return False
        return self._resolve_full_form(tok, next_tok) is not None

    def _apply_elision_omit(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
    ) -> ErrorResult | None:
        tok = tokens[idx]
        next_tok = tokens[idx + 1] if idx + 1 < len(tokens) else None
        full_form = self._resolve_full_form(tok, next_tok)
        if full_form is None:
            return None
        original = sentence[idx]
        corrupted = _match_capitalization(original, full_form)
        if corrupted == original:
            return None
        sentence[idx] = corrupted
        return ErrorResult(
            error_type=f"{self.name}_elision_omit",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=original,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{original}",
        )

    # -- euphonic_t_drop --------------------------------------------------

    def _can_apply_euphonic_t_drop(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        tok = tokens[idx]
        if tok.text.lower() != "-t":
            return False
        if tok.pos != "PRON":
            return False
        if idx == 0 or idx + 1 >= len(tokens):
            return False
        verb = tokens[idx - 1]
        if verb.pos not in ("VERB", "AUX"):
            return False
        pronoun = tokens[idx + 1]
        if pronoun.pos != "PRON":
            return False
        rule = _load_euphonic_t().get("trigger", {})
        pronouns = rule.get("pronouns", [])
        pronoun_text = pronoun.text.lower().lstrip("-")
        if pronoun_text not in pronouns:
            return False
        verb_form = verb.text.strip("-")
        if not verb_form:
            return False
        last_letter = verb_form[-1].lower()
        triggers = set(rule.get("verb_ending_triggers", []))
        if last_letter in triggers:
            return True
        # BDL-noted irregular analogy: vaincre/convaincre take -t- despite a
        # 3sg form ending in "c" (rule.get("irregular_note") documents this;
        # we key off the lemma directly rather than re-parsing the note).
        return verb.lemma in {"vaincre", "convaincre"}

    def _apply_euphonic_t_drop(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
    ) -> ErrorResult | None:
        if idx - 1 in modified:
            # The $APPEND fix tag anchors at idx-1 (an untouched token, by
            # WordOmissionHandler convention). If another handler already
            # corrupted idx-1, anchoring here would silently overwrite its
            # $REPLACE tag, leaving that corruption uncorrectable.
            return None
        deleted = sentence[idx]
        del sentence[idx]
        return ErrorResult(
            error_type=f"{self.name}_euphonic_t_drop",
            category=self.category,
            start_idx=idx - 1,
            end_idx=idx - 1,
            original=deleted,
            corrupted="",
            fix_tag=f"$APPEND_{deleted}",
        )

    # -- protocol ----------------------------------------------------------

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx < 0 or idx >= len(tokens):
            return False
        return self._can_apply_elision_omit(tokens, idx) or self._can_apply_euphonic_t_drop(
            tokens, idx
        )

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        if self._can_apply_euphonic_t_drop(tokens, idx):
            return self._apply_euphonic_t_drop(tokens, sentence, idx, modified)
        if self._can_apply_elision_omit(tokens, idx):
            return self._apply_elision_omit(tokens, sentence, idx)
        return None
