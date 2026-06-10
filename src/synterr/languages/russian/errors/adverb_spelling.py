"""Russian adverb spelling handler — solid/separate/hyphen confusion.

Covers LoRuGEC rule: "Слитное, раздельное и дефисное написание наречий"
Rozental §53–58.

Common error direction: writing a solid adverb as two words, or vice versa.
Examples:
- "наутро" (solid) → "на утро" (separate) — error
- "на лету" (separate) → "налету" (solid) — error
- "по-русски" (hyphen) → "по русски" (separate) — error
"""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# Adverb solid → separate confusion pairs
# Format: solid_form → (preposition, remainder)
# Error direction: correct solid → incorrect separate
# =============================================================================

_SOLID_TO_SEPARATE: dict[str, tuple[str, str]] = {
    # §53: наречия, образованные от существительных с предлогами
    "вверх": ("в", "верх"),
    "вверху": ("в", "верху"),
    "вглубь": ("в", "глубь"),
    "вдаль": ("в", "даль"),
    "вдали": ("в", "дали"),
    "вконец": ("в", "конец"),
    "вкось": ("в", "кось"),
    "вкратце": ("в", "кратце"),
    "вместе": ("в", "месте"),
    "вначале": ("в", "начале"),
    "вниз": ("в", "низ"),
    "внизу": ("в", "низу"),
    "вновь": ("в", "новь"),
    "вовремя": ("во", "время"),
    "воистину": ("во", "истину"),
    "вослед": ("во", "след"),
    "впереди": ("в", "переди"),
    "вплотную": ("в", "плотную"),
    # NOT listed: вполне — suffix-derived (полный), absent from §53–58;
    # "в полне" unattested in RLC.
    "вправо": ("в", "право"),
    "впредь": ("в", "предь"),
    "вприпрыжку": ("в", "припрыжку"),
    "впрок": ("в", "прок"),
    "вразброс": ("в", "разброс"),
    "врасплох": ("в", "расплох"),
    "вскоре": ("в", "скоре"),
    "вслед": ("в", "след"),
    "вслух": ("в", "слух"),
    "втайне": ("в", "тайне"),
    "добела": ("до", "бела"),
    # NOT listed: довольно — suffix-derived from довольный, not a §53
    # prep+noun/short-adj formation; "до вольно" is non-learner garbage.
    "доныне": ("до", "ныне"),
    "досуха": ("до", "суха"),
    "задаром": ("за", "даром"),
    "заодно": ("за", "одно"),
    "зачастую": ("за", "частую"),
    "извне": ("из", "вне"),
    "издалека": ("из", "далека"),
    "издали": ("из", "дали"),
    "наверх": ("на", "верх"),
    "наверху": ("на", "верху"),
    "навеки": ("на", "веки"),
    "навстречу": ("на", "встречу"),
    "наглухо": ("на", "глухо"),
    "надвое": ("на", "двое"),
    "назад": ("на", "зад"),
    "наизусть": ("на", "изусть"),
    "накануне": ("на", "кануне"),
    "наконец": ("на", "конец"),
    "налево": ("на", "лево"),
    "намного": ("на", "много"),
    "наоборот": ("на", "оборот"),
    "наотрез": ("на", "отрез"),
    "наперёд": ("на", "перёд"),
    "наполовину": ("на", "половину"),
    "направо": ("на", "право"),
    # NOT listed: напрасно — suffix-derived from напрасный; на- here is
    # part of the adjective root chain, not a §53 prefix.
    "напрокат": ("на", "прокат"),
    "напротив": ("на", "против"),
    "наружу": ("на", "ружу"),
    "насквозь": ("на", "сквозь"),
    "наспех": ("на", "спех"),
    "настежь": ("на", "стежь"),
    "настолько": ("на", "столько"),
    "насухо": ("на", "сухо"),
    "наугад": ("на", "угад"),
    "наутро": ("на", "утро"),
    "наяву": ("на", "яву"),
    # NOT listed: отовсюду — ото- + всюду is a §56 п.1 prefix+adverb
    # formation (cf. донельзя, навсегда); learners do not split these,
    # and the old ("от", "овсюду") cut landed inside the prefix.
    "отчасти": ("от", "части"),
    "поблизости": ("по", "близости"),
    "поверх": ("по", "верх"),
    "подолгу": ("по", "долгу"),
    "подряд": ("по", "дряд"),
    "позади": ("по", "зади"),
    "помимо": ("по", "мимо"),
    "понапрасну": ("по", "напрасну"),
    "понемногу": ("по", "немногу"),
    "поневоле": ("по", "неволе"),
    # NOT listed: поочерёдно, попарно — -о-suffix adverbs from adjectives
    # (поочерёдный, парный), absent from all §53–58 lists.
    "пополам": ("по", "полам"),
    "поровну": ("по", "ровну"),
    "посередине": ("по", "середине"),
    "потихоньку": ("по", "тихоньку"),
    "сбоку": ("с", "боку"),
    "сверху": ("с", "верху"),
    "снизу": ("с", "низу"),
    "сначала": ("с", "начала"),
    "снаружи": ("с", "наружи"),
    "сослепу": ("со", "слепу"),
    "сразу": ("с", "разу"),
}


# =============================================================================
# Adverb hyphen → separate confusion
# Format: hyphenated_form → (prefix, remainder)
# §56: наречия с дефисом: по-...-ому/-ему/-ски/-цки/-ьи, во-первых, etc.
# =============================================================================

_HYPHEN_TO_SEPARATE: dict[str, tuple[str, ...]] = {
    "по-русски": ("по", "русски"),
    "по-английски": ("по", "английски"),
    "по-немецки": ("по", "немецки"),
    "по-французски": ("по", "французски"),
    "по-новому": ("по", "новому"),
    "по-старому": ("по", "старому"),
    "по-моему": ("по", "моему"),
    "по-твоему": ("по", "твоему"),
    "по-своему": ("по", "своему"),
    "по-нашему": ("по", "нашему"),
    "по-вашему": ("по", "вашему"),
    "по-прежнему": ("по", "прежнему"),
    "по-настоящему": ("по", "настоящему"),
    "по-хорошему": ("по", "хорошему"),
    "по-разному": ("по", "разному"),
    "по-другому": ("по", "другому"),
    "по-иному": ("по", "иному"),
    "по-видимому": ("по", "видимому"),
    "по-человечески": ("по", "человечески"),
    "по-братски": ("по", "братски"),
    "по-дружески": ("по", "дружески"),
    "по-хозяйски": ("по", "хозяйски"),
    "по-волчьи": ("по", "волчьи"),
    "по-медвежьи": ("по", "медвежьи"),
    "во-первых": ("во", "первых"),
    "во-вторых": ("во", "вторых"),
    "в-третьих": ("в", "третьих"),
    "в-четвёртых": ("в", "четвёртых"),
    "в-пятых": ("в", "пятых"),
    "где-то": ("где", "то"),
    "куда-то": ("куда", "то"),
    "когда-то": ("когда", "то"),
    "как-то": ("как", "то"),
    "откуда-то": ("откуда", "то"),
    "где-нибудь": ("где", "нибудь"),
    "куда-нибудь": ("куда", "нибудь"),
    "когда-нибудь": ("когда", "нибудь"),
    "как-нибудь": ("как", "нибудь"),
    "где-либо": ("где", "либо"),
    "куда-либо": ("куда", "либо"),
    "когда-либо": ("когда", "либо"),
    "как-либо": ("как", "либо"),
    "кое-как": ("кое", "как"),
    "кое-где": ("кое", "где"),
    "кое-куда": ("кое", "куда"),
    "кое-когда": ("кое", "когда"),
    "мало-помалу": ("мало", "помалу"),
    "еле-еле": ("еле", "еле"),
    "чуть-чуть": ("чуть", "чуть"),
    # Multi-hyphen adverb: the learner error is full de-hyphenation
    # ("точь в точь", three tokens), not a partial cut ("точь-в точь").
    "точь-в-точь": ("точь", "в", "точь"),
    # NOT listed: бок-о-бок — the norm is fully separate "бок о бок"
    # (§58 п.1); the hyphenated form is itself the error, generated by
    # _TRIGRAM_SEPARATE_TO_HYPHEN below.
    "нежданно-негаданно": ("нежданно", "негаданно"),
    "подобру-поздорову": ("подобру", "поздорову"),
}


# §56 п.7 прим.1–2: these spatial/temporal words keep SOLID spelling even
# as adverbial prepositions with a governed noun ("внизу двери", "наверху
# блаженства", "посередине комнаты"), while the separate spelling is also
# sanctioned with a governed noun ("в глубь океана"). Merging the separate
# phrase is therefore not reliably an error → merge direction disabled.
# Forward solid→separate stays (splitting the bare adverb IS an error).
_NO_MERGE: frozenset[str] = frozenset(
    {
        "посередине",
        "наверху",
        "внизу",
        "вверху",
        "сбоку",
        "сверху",
        "снизу",
        "вглубь",
        "вдаль",
        "вдали",
        "поверх",
        "позади",
        "впереди",
    }
)

# Merge pairs whose second token has a concrete-noun homograph: skip the
# merge when the analyzed lemma is the homograph. "на веки" with lemma
# веко (eyelids) merges into the fully grammatical "навеки" — a fluent
# meaning change, not a spelling error (§56 п.7 прим.1 concerns век 'age').
_MERGE_BLOCKED_LEMMAS: dict[tuple[str, str], frozenset[str]] = {
    ("на", "веки"): frozenset({"веко"}),
}

# Reverse lookups: (prep, remainder) → solid form
_SEPARATE_TO_SOLID: dict[tuple[str, str], str] = {}
for _solid, (_prep, _rem) in _SOLID_TO_SEPARATE.items():
    if _solid not in _NO_MERGE:
        _SEPARATE_TO_SOLID[(_prep, _rem)] = _solid

_SEPARATE_TO_HYPHEN: dict[tuple[str, str], str] = {}
for _hyph, _parts in _HYPHEN_TO_SEPARATE.items():
    if len(_parts) == 2:
        _SEPARATE_TO_HYPHEN[(_parts[0], _parts[1])] = _hyph

# Three-token separate phrases whose hyphenation is a real learner error
# (by analogy with точь-в-точь). The separate form is the norm (§58 п.1:
# "бок о бок"); the hyphenated output is the corruption.
_TRIGRAM_SEPARATE_TO_HYPHEN: dict[tuple[str, str, str], str] = {
    ("бок", "о", "бок"): "бок-о-бок",
}

# POS allowlist for splitting a solid adverb. The listed words function as
# adverbs or adverbial prepositions (помимо, вслед, напротив → ADP) or
# discourse particles; a NOUN/ADJ reading means a homograph (подряд
# 'contract') that must not be split.
_SPLITTABLE_POS: frozenset[str] = frozenset({"ADV", "ADP", "PART"})

# Verbs governing подряд as a noun ('contract'): stanza tags that reading
# ADV too, so the POS gate alone cannot catch it — context guard needed.
_PODRYAD_GOVERNORS: frozenset[str] = frozenset(
    {
        "выиграть",
        "выигрывать",
        "получить",
        "получать",
        "заключить",
        "заключать",
        "подписать",
        "подписывать",
        "отдать",
        "отдавать",
        "взять",
        "брать",
        "выполнить",
        "выполнять",
    }
)


class AdverbSpellingHandler:
    """Corrupt adverb spelling: solid↔separate, hyphen↔separate.

    Subtypes:
    - adverb_solid_to_separate: Split solid adverb into prep + noun
    - adverb_separate_to_solid: Merge prep + noun into solid adverb
    - adverb_hyphen_to_separate: Remove hyphen from adverb
    - adverb_separate_to_hyphen: Add hyphen to separate adverb
    """

    name = "adverb_spelling"
    subtypes = [
        "adverb_solid_to_separate",
        "adverb_separate_to_solid",
        "adverb_hyphen_to_separate",
        "adverb_separate_to_hyphen",
    ]
    category = "SPELL"
    changes_length = True

    DEFAULT_WEIGHTS = {
        "adverb_solid_to_separate": 30,
        "adverb_separate_to_solid": 30,
        "adverb_hyphen_to_separate": 20,
        "adverb_separate_to_hyphen": 20,
    }

    def __init__(self) -> None:
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()
        self._enabled_subtypes: set[str] | None = None

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        self._weights = self.DEFAULT_WEIGHTS.copy()
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        """Restrict to specific subtypes (used by targeted SFT / CLI :subtype).

        When set, apply() returns None if the weighted choice falls outside
        the enabled set — letting the pipeline try another position instead
        of emitting a mislabeled error.
        """
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    @staticmethod
    def _solid_split_ok(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Guard the solid→separate direction against noun homographs."""
        token = tokens[idx]
        if token.pos not in _SPLITTABLE_POS:
            return False
        if token.text.lower() == "подряд":
            # Noun reading 'contract' (подряд на ремонт; выиграть подряд):
            # splitting it yields the non-word "по дряд" (§56 п.6 lists
            # подряд as adverb only).
            if idx + 1 < len(tokens) and tokens[idx + 1].text.lower() == "на":
                return False
            if idx > 0 and tokens[idx - 1].lemma.lower() in _PODRYAD_GOVERNORS:
                return False
        return True

    @staticmethod
    def _merge_ok(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Guard merges against live syntactic prep+noun phrases."""
        nxt = tokens[idx + 1]
        pair = (tokens[idx].text.lower(), nxt.text.lower())
        blocked = _MERGE_BLOCKED_LEMMAS.get(pair)
        if blocked and nxt.lemma.lower() in blocked:
            return False
        # Dep-tree guard (requires use_depparse): a noun with dependents of
        # its own ("в начале осени") heads a live NP — merging may produce
        # sanctioned spelling or destroy government; skip.
        return not any(
            t.head_idx == idx + 1 for i, t in enumerate(tokens) if i != idx
        )

    @staticmethod
    def _to_merge_blocked(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Guard где/когда/как/куда + 'то' merges: -то hyphenation (§57 п.3)
        applies to the indefinite particle only, not the pronoun/demonstrative
        то ("то и дело", "то же", correlative "…, как то советовал отец")."""
        nxt = tokens[idx + 1]
        if nxt.text.lower() != "то":
            return False
        if nxt.pos in ("PRON", "DET"):
            return True
        if idx + 2 < len(tokens):
            after = tokens[idx + 2]
            after_lower = after.text.lower()
            if after_lower in ("же", "что", "самое", ":"):
                return True
            if (
                after_lower == "и"
                and idx + 3 < len(tokens)
                and tokens[idx + 3].text.lower() == "дело"
            ):
                return True
            # Correlative clause: comma before + finite verb right after то
            # ("Сделай так, как то советовал отец") — merging reads as
            # valid Russian with changed meaning.
            if idx > 0 and tokens[idx - 1].text == "," and after.pos == "VERB":
                return True
        return False

    def _merge_candidates_ok(
        self, tokens: Sequence[AnalyzedToken], pair: tuple[str, str], idx: int
    ) -> bool:
        if not self._merge_ok(tokens, idx):
            return False
        return not (pair[1] == "то" and self._to_merge_blocked(tokens, idx))

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        text_lower = tokens[idx].text.lower()
        # Forward: solid/hyphen → separate
        if text_lower in _SOLID_TO_SEPARATE and self._solid_split_ok(tokens, idx):
            return True
        if text_lower in _HYPHEN_TO_SEPARATE:
            return True
        # Reverse: two adjacent tokens → merge into solid/hyphen
        if idx < len(tokens) - 1:
            pair = (text_lower, tokens[idx + 1].text.lower())
            if (
                pair in _SEPARATE_TO_SOLID or pair in _SEPARATE_TO_HYPHEN
            ) and self._merge_candidates_ok(tokens, pair, idx):
                return True
        # Reverse: three tokens → hyphenate (бок о бок → бок-о-бок)
        if idx < len(tokens) - 2:
            trigram = (
                text_lower,
                tokens[idx + 1].text.lower(),
                tokens[idx + 2].text.lower(),
            )
            if trigram in _TRIGRAM_SEPARATE_TO_HYPHEN:
                return True
        return False

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module
        word = sentence[idx]
        text_lower = word.lower()

        candidates: list[tuple[str, float]] = []
        if text_lower in _SOLID_TO_SEPARATE and self._solid_split_ok(tokens, idx):
            candidates.append(
                ("adverb_solid_to_separate", self._weights["adverb_solid_to_separate"])
            )
        if text_lower in _HYPHEN_TO_SEPARATE:
            candidates.append(
                (
                    "adverb_hyphen_to_separate",
                    self._weights["adverb_hyphen_to_separate"],
                )
            )
        # Reverse: merge two tokens into one. Look up the LIVE sentence text
        # (not the analyzed tokens) and refuse to swallow a neighbor that
        # another handler already corrupted — its recorded edit would point
        # at text destroyed by the merge.
        merge_pair: tuple[str, str] | None = None
        if (
            idx < len(tokens) - 1
            and idx + 1 < len(sentence)
            and idx + 1 not in modified
        ):
            merge_pair = (text_lower, sentence[idx + 1].lower())
            if self._merge_candidates_ok(tokens, merge_pair, idx):
                if merge_pair in _SEPARATE_TO_SOLID:
                    candidates.append(
                        (
                            "adverb_separate_to_solid",
                            self._weights["adverb_separate_to_solid"],
                        )
                    )
                if merge_pair in _SEPARATE_TO_HYPHEN:
                    candidates.append(
                        (
                            "adverb_separate_to_hyphen",
                            self._weights["adverb_separate_to_hyphen"],
                        )
                    )
        # Reverse: hyphenate a three-token phrase (бок о бок → бок-о-бок)
        merge_trigram: tuple[str, str, str] | None = None
        if (
            idx < len(tokens) - 2
            and idx + 2 < len(sentence)
            and idx + 1 not in modified
            and idx + 2 not in modified
        ):
            trigram = (
                text_lower,
                sentence[idx + 1].lower(),
                sentence[idx + 2].lower(),
            )
            if trigram in _TRIGRAM_SEPARATE_TO_HYPHEN:
                merge_trigram = trigram
                candidates.append(
                    (
                        "adverb_separate_to_hyphen",
                        self._weights["adverb_separate_to_hyphen"],
                    )
                )

        if self._enabled_subtypes is not None:
            candidates = [c for c in candidates if c[0] in self._enabled_subtypes]

        if not candidates:
            return None

        # weight 0 means excluded — drop before the draw so an all-zero
        # candidate set skips instead of crashing rng.choices
        candidates = [c for c in candidates if c[1] > 0]
        if not candidates:
            return None

        subtypes, weights = zip(*candidates, strict=False)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        if chosen == "adverb_solid_to_separate":
            prep, remainder = _SOLID_TO_SEPARATE[text_lower]
            part1 = prep[0].upper() + prep[1:] if word[0].isupper() else prep
            part2 = remainder
            original = sentence[idx]
            sentence[idx] = part1
            sentence.insert(idx + 1, part2)
            return ErrorResult(
                error_type="adverb_spelling_adverb_solid_to_separate",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=original,
                corrupted=f"{part1} {part2}",
                fix_tag=f"$MERGE_{original}",
            )

        elif chosen == "adverb_hyphen_to_separate":
            parts = list(_HYPHEN_TO_SEPARATE[text_lower])
            if word[0].isupper():
                parts[0] = parts[0][0].upper() + parts[0][1:]
            original = sentence[idx]
            sentence[idx] = parts[0]
            for offset, part in enumerate(parts[1:], start=1):
                sentence.insert(idx + offset, part)
            return ErrorResult(
                error_type="adverb_spelling_adverb_hyphen_to_separate",
                category=self.category,
                start_idx=idx,
                end_idx=idx + len(parts) - 1,
                original=original,
                corrupted=" ".join(parts),
                fix_tag=f"$MERGE_{original}",
            )

        elif chosen == "adverb_separate_to_solid":
            if merge_pair is None:
                return None
            solid = _SEPARATE_TO_SOLID[merge_pair]
            original_1 = sentence[idx]
            original_2 = sentence[idx + 1]
            if original_1[0].isupper():
                solid = solid[0].upper() + solid[1:]
            sentence[idx] = solid
            del sentence[idx + 1]
            return ErrorResult(
                error_type="adverb_spelling_adverb_separate_to_solid",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=f"{original_1} {original_2}",
                corrupted=solid,
                fix_tag=f"$SPLIT_{original_1}_{original_2}",
            )

        elif chosen == "adverb_separate_to_hyphen":
            if merge_trigram is not None and (
                merge_pair is None or merge_pair not in _SEPARATE_TO_HYPHEN
            ):
                hyphenated = _TRIGRAM_SEPARATE_TO_HYPHEN[merge_trigram]
                originals = [sentence[idx], sentence[idx + 1], sentence[idx + 2]]
                if originals[0][0].isupper():
                    hyphenated = hyphenated[0].upper() + hyphenated[1:]
                sentence[idx] = hyphenated
                del sentence[idx + 1 : idx + 3]
                return ErrorResult(
                    error_type="adverb_spelling_adverb_separate_to_hyphen",
                    category=self.category,
                    start_idx=idx,
                    end_idx=idx + 2,
                    original=" ".join(originals),
                    corrupted=hyphenated,
                    fix_tag="$SPLIT_" + "_".join(originals),
                )
            if merge_pair is None:
                return None
            hyphenated = _SEPARATE_TO_HYPHEN[merge_pair]
            original_1 = sentence[idx]
            original_2 = sentence[idx + 1]
            if original_1[0].isupper():
                hyphenated = hyphenated[0].upper() + hyphenated[1:]
            sentence[idx] = hyphenated
            del sentence[idx + 1]
            return ErrorResult(
                error_type="adverb_spelling_adverb_separate_to_hyphen",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=f"{original_1} {original_2}",
                corrupted=hyphenated,
                fix_tag=f"$SPLIT_{original_1}_{original_2}",
            )

        return None
