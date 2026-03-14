"""Russian function word spelling handler.

Covers Rozental §59–72 (sp_function L1 tag):
- не/ни attachment/detachment with nouns, adjectives, verbs, participles
- Conjunction split/merge: чтобы/что бы, также/так же, зато/за то, etc.
- Particle spelling: -таки hyphen errors

This handler changes_length=True because split/merge operations add/remove tokens.
"""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.resources import get_morpheme_analyzer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

# =============================================================================
# CONJUNCTION/PARTICLE SPLIT/MERGE PAIRS
# Solid form → two-word form (and reverse)
# Direction of corruption depends on what we find in the sentence.
# =============================================================================

# Solid → split: "чтобы" → "что бы"
SOLID_TO_SPLIT: dict[str, tuple[str, str]] = {
    "чтобы": ("что", "бы"),
    "также": ("так", "же"),
    "тоже": ("то", "же"),
    "зато": ("за", "то"),
    "оттого": ("от", "того"),
    "отчего": ("от", "чего"),
    "потому": ("по", "тому"),
    "поэтому": ("по", "этому"),
    "причём": ("при", "чём"),
    "причем": ("при", "чем"),
    "притом": ("при", "том"),
    "итак": ("и", "так"),
    "зачем": ("за", "чем"),
    "затем": ("за", "тем"),
    "почему": ("по", "чему"),
    # "отчасти" removed: not a §61 conjunction confusion (it's §56 наречие)
}

# Reverse: split → solid (for detecting two-word sequences to merge)
# Only include pairs where merging creates a real confusion
SPLIT_TO_SOLID: dict[tuple[str, str], str] = {
    ("что", "бы"): "чтобы",
    ("так", "же"): "также",
    ("то", "же"): "тоже",
    ("за", "то"): "зато",
    ("от", "того"): "оттого",
    ("от", "чего"): "отчего",
    ("при", "чём"): "причём",
    ("при", "чем"): "причем",
    ("при", "том"): "притом",
    # ("и", "так") removed: "и так" is far more common than conjunction "итак",
    # merging it produces correct text most of the time
}

# не/ни + POS combinations where attachment/detachment is confusable
# POS tags where не can be written solid (не + word → неword)
# VERB included: "не хочу" → "нехочу" is a common LoRuGEC error (§69)
NE_ATTACHABLE_POS = {"NOUN", "ADJ", "ADV", "VERB"}

# POS tags where не- can be a real detachable prefix
# VERB included: "невзлюбил" → "не взлюбил" (§69 exceptions: ненавидеть, негодовать, etc.)
NE_DETACHABLE_POS = {"ADJ", "NOUN", "ADV", "VERB"}

# -таки: should be hyphenated after certain words
# Error: remove hyphen or detach
TAKI_TRIGGER_POS = {"VERB", "ADV", "PART"}


class FunctionSpellingHandler:
    """Corrupt function word spelling: не/ни, conjunctions, particles.

    Subtypes:
    - ne_attachment: Merge "не word" → "неword" (incorrect solid writing)
    - ne_detachment: Split "неword" → "не word" (incorrect separate writing)
    - conjunction_split: Split solid conjunction: "чтобы" → "что бы"
    - conjunction_merge: Merge separate words: "что бы" → "чтобы"
    - taki_hyphen: Remove or misplace -таки hyphen
    """

    name = "function_spelling"
    subtypes = [
        "ne_attachment",
        "ne_detachment",
        "conjunction_split",
        "conjunction_merge",
        "taki_hyphen",
    ]
    category = "SPELL"
    changes_length = True

    DEFAULT_WEIGHTS = {
        "ne_attachment": 25,
        "ne_detachment": 25,
        "conjunction_split": 25,
        "conjunction_merge": 20,
        "taki_hyphen": 5,
    }

    def __init__(self):
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        self._weights = self.DEFAULT_WEIGHTS.copy()
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        text_lower = token.text.lower()

        # Solid conjunction that can be split
        if text_lower in SOLID_TO_SPLIT:
            return True

        # Two-word sequence that can be merged
        if idx < len(tokens) - 1:
            pair = (text_lower, tokens[idx + 1].text.lower())
            if pair in SPLIT_TO_SOLID:
                return True

        # "не" / "ни" before attachable POS
        if text_lower in ("не", "ни") and idx < len(tokens) - 1:
            next_tok = tokens[idx + 1]
            if next_tok.pos in NE_ATTACHABLE_POS and next_tok.text.isalpha():
                return True

        # Word starting with не-/ни- that can be detached
        if (
            len(text_lower) > 3
            and text_lower[:2] in ("не", "ни")
            and token.pos in NE_DETACHABLE_POS
        ):
            return True

        # -таки patterns (avoid matching "атаки", "такие", etc.)
        if "-таки" in text_lower:
            return True
        if text_lower == "таки" and idx > 0:
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
        token = tokens[idx]
        text_lower = token.text.lower()

        # Collect applicable subtypes with weights
        candidates: list[tuple[str, float]] = []

        if text_lower in SOLID_TO_SPLIT:
            candidates.append(("conjunction_split", self._weights["conjunction_split"]))

        if idx < len(tokens) - 1:
            pair = (text_lower, tokens[idx + 1].text.lower())
            if pair in SPLIT_TO_SOLID:
                candidates.append(("conjunction_merge", self._weights["conjunction_merge"]))

        if text_lower in ("не", "ни") and idx < len(tokens) - 1:
            next_tok = tokens[idx + 1]
            if next_tok.pos in NE_ATTACHABLE_POS and next_tok.text.isalpha():
                candidates.append(("ne_attachment", self._weights["ne_attachment"]))

        if (
            len(text_lower) > 3
            and text_lower[:2] in ("не", "ни")
            and token.pos in NE_DETACHABLE_POS
        ):
            candidates.append(("ne_detachment", self._weights["ne_detachment"]))

        if "-таки" in text_lower or (text_lower == "таки" and idx > 0):
            candidates.append(("taki_hyphen", self._weights["taki_hyphen"]))

        if not candidates:
            return None

        # Weighted selection
        subtypes, weights = zip(*candidates)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        if chosen == "conjunction_split":
            return self._apply_conjunction_split(token, sentence, idx)
        elif chosen == "conjunction_merge":
            return self._apply_conjunction_merge(tokens, sentence, idx)
        elif chosen == "ne_attachment":
            return self._apply_ne_attachment(tokens, sentence, idx)
        elif chosen == "ne_detachment":
            return self._apply_ne_detachment(token, sentence, idx)
        elif chosen == "taki_hyphen":
            return self._apply_taki(tokens, sentence, idx)

        return None

    def _apply_conjunction_split(
        self, token: AnalyzedToken, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Split solid conjunction: чтобы → что бы."""
        text_lower = token.text.lower()
        parts = SOLID_TO_SPLIT.get(text_lower)
        if parts is None:
            return None

        part1, part2 = parts
        original = sentence[idx]

        # Preserve capitalization of first letter
        if original[0].isupper():
            part1 = part1[0].upper() + part1[1:]

        sentence[idx] = part1
        sentence.insert(idx + 1, part2)

        return ErrorResult(
            error_type="function_spelling_conjunction_split",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=original,
            corrupted=f"{part1} {part2}",
            fix_tag=f"$MERGE_{original}",
        )

    def _apply_conjunction_merge(
        self, tokens: Sequence[AnalyzedToken], sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Merge separate words: что бы → чтобы."""
        if idx >= len(tokens) - 1:
            return None

        text_lower = tokens[idx].text.lower()
        next_lower = tokens[idx + 1].text.lower()
        pair = (text_lower, next_lower)
        solid = SPLIT_TO_SOLID.get(pair)
        if solid is None:
            return None

        original_1 = sentence[idx]
        original_2 = sentence[idx + 1]

        # Preserve capitalization
        if original_1[0].isupper():
            solid = solid[0].upper() + solid[1:]

        sentence[idx] = solid
        del sentence[idx + 1]

        return ErrorResult(
            error_type="function_spelling_conjunction_merge",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=f"{original_1} {original_2}",
            corrupted=solid,
            fix_tag=f"$SPLIT_{original_1}_{original_2}",
        )

    def _apply_ne_attachment(
        self, tokens: Sequence[AnalyzedToken], sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Merge "не word" → "неword" (incorrect solid writing)."""
        if idx >= len(tokens) - 1:
            return None

        particle = sentence[idx]  # не or ни
        particle_lower = particle.lower()
        next_tok = tokens[idx + 1]
        next_word = sentence[idx + 1]

        if not next_word.isalpha():
            return None

        # ни only forms solid words in closed-class pronouns/adverbs (никто, нигде)
        # Don't productively attach ни to arbitrary words
        if particle_lower == "ни":
            return None

        merged_lower = particle_lower + next_word.lower()
        # For VERB: skip word_is_known — merging is intentionally wrong (§69)
        # "не хочу" → "нехочу" is a real learner error
        if next_tok.pos != "VERB":
            # Only merge if the result is a real word (prevents некошка, нестол)
            analyzer = get_morpheme_analyzer()
            if not analyzer.word_is_known(merged_lower):
                return None

        merged = merged_lower
        if particle[0].isupper():
            merged = merged[0].upper() + merged[1:]

        original_particle = sentence[idx]
        original_word = sentence[idx + 1]

        sentence[idx] = merged
        del sentence[idx + 1]

        return ErrorResult(
            error_type="function_spelling_ne_attachment",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=f"{original_particle} {original_word}",
            corrupted=merged,
            fix_tag=f"$SPLIT_{original_particle}_{original_word}",
        )

    def _apply_ne_detachment(
        self, token: AnalyzedToken, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Split "неword" → "не word" (incorrect separate writing)."""
        text = sentence[idx]
        text_lower = text.lower()

        if len(text_lower) <= 3:
            return None

        prefix = text_lower[:2]  # "не" or "ни"
        if prefix not in ("не", "ни"):
            return None

        remainder_lower = text_lower[2:]

        analyzer = get_morpheme_analyzer()

        # Validate: не/ни must be a real prefix (prevents нервный→не рвный)
        has_pfx = analyzer.has_prefix(text_lower, prefix)
        if has_pfx is None:
            # Word not in morpheme dict at all — don't guess
            # This prevents неделя→не деля, невеста→не веста, etc.
            return None
        if has_pfx is False:
            # Morpheme dict says not a prefix — but dict can be wrong
            # (несчастье segmented without не- prefix). Allow if remainder
            # is a real word.
            if not analyzer.word_is_known(remainder_lower):
                return None

        # For VERB with confirmed prefix: allow split even if remainder is not
        # independently known (невзлюбить→не взлюбить: "взлюбить" may not exist alone)
        if token.pos != "VERB" or has_pfx is not True:
            # Validate: remainder must be a real word (prevents нефть→не фть)
            if not analyzer.word_is_known(remainder_lower):
                return None

        rest = text[2:]  # preserve original case of the rest

        # Preserve case of prefix
        if text[0].isupper():
            particle = prefix[0].upper() + prefix[1:]
            rest = rest[0].lower() + rest[1:] if rest else rest
        else:
            particle = prefix

        original = sentence[idx]
        sentence[idx] = particle
        sentence.insert(idx + 1, rest)

        return ErrorResult(
            error_type="function_spelling_ne_detachment",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=original,
            corrupted=f"{particle} {rest}",
            fix_tag=f"$MERGE_{original}",
        )

    def _apply_taki(
        self, tokens: Sequence[AnalyzedToken], sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Corrupt -таки hyphenation."""
        text = sentence[idx]
        text_lower = text.lower()

        # Word contains "-таки" → remove hyphen (detach)
        if "-таки" in text_lower:
            original = text
            # Remove hyphen: "всё-таки" → "всё таки"
            hyphen_pos = text.lower().find("-таки")
            base = text[:hyphen_pos]
            sentence[idx] = base
            sentence.insert(idx + 1, "таки")

            return ErrorResult(
                error_type="function_spelling_taki_hyphen",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=original,
                corrupted=f"{base} таки",
                fix_tag=f"$MERGE_{original}",
            )

        # Standalone "таки" after verb/adv/particle → should have been hyphenated
        # We can't easily fix this direction (would need to check prev word),
        # so skip standalone таки for now
        return None
