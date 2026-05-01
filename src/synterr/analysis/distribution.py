"""Analyze M2 files to extract error type distributions."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Regex for M2 annotation lines
# Format: A start end|||error_type|||correction|||REQUIRED|||-NONE-|||annotator_id
M2_ANNOTATION_PATTERN = re.compile(r"^A (\d+) (\d+)\|\|\|([^|]+)\|\|\|(.*)$")

# Error type mappings to synterr categories
# Russian error types from RULEC-GEC, GERA, RuLang-8
ERROR_TYPE_TO_CATEGORY = {
    # =========================================================================
    # SPELLING/ORTHOGRAPHY → SPELL
    # =========================================================================
    "Орфография": "SPELL",
    "Spelling": "SPELL",
    "ORTH": "SPELL",
    "SPELL": "SPELL",
    # GERA spelling types (S: prefix)
    "S:ORTH": "SPELL",
    "S:TYPO": "SPELL",
    "S:LETTER:CASE": "SPELL",  # Capitalization
    "S:SPACE": "SPELL",
    "S:HYPHEN": "SPELL",
    # =========================================================================
    # MORPHOLOGICAL - NOUNS → MORPH:noun_*
    # =========================================================================
    "Сущ.:Падеж": "MORPH:noun_case",
    "Сущ.:Число": "MORPH:noun_number",
    "Сущ.:Род": "MORPH:noun_gender",
    "Сущ.:Др.": "MORPH:noun_other",
    # GERA noun types (G:NOUN: prefix)
    "G:NOUN:CASE": "MORPH:noun_case",
    "G:NOUN:NUM": "MORPH:noun_number",
    "G:NOUN:GENDER": "MORPH:noun_gender",
    "G:NOUN:OTHER": "MORPH:noun_other",
    "NOUN:CASE": "MORPH:noun_case",
    "NOUN:NUM": "MORPH:noun_number",
    # =========================================================================
    # MORPHOLOGICAL - ADJECTIVES → MORPH:adj_*
    # =========================================================================
    "Прил.:Падеж": "MORPH:adj_case",
    "Прил.:Число": "MORPH:adj_number",
    "Прил.:Род": "MORPH:adj_gender",
    "Прил.:Др.": "MORPH:adj_other",
    # GERA adjective types (G:ADJ: prefix)
    "G:ADJ:CASE": "MORPH:adj_case",
    "G:ADJ:NUM": "MORPH:adj_number",
    "G:ADJ:GENDER": "MORPH:adj_gender",
    "G:ADJ:OTHER": "MORPH:adj_other",
    "G:ADJ:FORM": "MORPH:adj_other",
    "ADJ:CASE": "MORPH:adj_case",
    "ADJ:NUM": "MORPH:adj_number",
    "ADJ:GENDER": "MORPH:adj_gender",
    # =========================================================================
    # MORPHOLOGICAL - VERBS → MORPH:verb_*
    # =========================================================================
    "Глагол:Время": "MORPH:verb_tense",
    "Глагол:Вид": "MORPH:verb_aspect",
    "Глагол:Число/Лицо": "MORPH:verb_person_number",
    "Глагол:Залог": "MORPH:verb_voice",
    "Глагол:Др.": "MORPH:verb_other",
    # GERA verb types (G:VERB: prefix)
    "G:VERB:TENSE": "MORPH:verb_tense",
    "G:VERB:ASPECT": "MORPH:verb_aspect",
    "G:VERB:NUM": "MORPH:verb_person_number",
    "G:VERB:PERS": "MORPH:verb_person_number",
    "G:VERB:VOICE": "MORPH:verb_voice",
    "G:VERB:FORM": "MORPH:verb_other",
    "G:VERB:OTHER": "MORPH:verb_other",
    "VERB:TENSE": "MORPH:verb_tense",
    "VERB:NUM": "MORPH:verb_person_number",
    "VERB:FORM": "MORPH:verb_other",
    # =========================================================================
    # MORPHOLOGICAL - OTHER PARTS OF SPEECH → MORPH:other
    # =========================================================================
    "G:PRON:CASE": "MORPH:other",
    "G:PRON:NUM": "MORPH:other",
    "G:PRON:GENDER": "MORPH:other",
    "G:NUM:CASE": "MORPH:other",
    "G:NUM:GENDER": "MORPH:other",
    "G:PART:OTHER": "MORPH:other",
    "G:ADV:OTHER": "MORPH:other",
    "G:MORPH": "MORPH:other",
    # =========================================================================
    # STRUCTURAL → OTHER:insert/delete
    # =========================================================================
    "Вставить": "OTHER:insert",
    "Убрать": "OTHER:delete",
    "MISSING": "OTHER:insert",
    "UNNECESSARY": "OTHER:delete",
    "LACK": "OTHER:insert",  # GERA: missing element
    "EXCESS": "OTHER:delete",  # GERA: extra element
    # =========================================================================
    # LEXICAL → OTHER:lexical*
    # =========================================================================
    "Заменить": "OTHER:lexical",
    "Лексика:замена": "OTHER:lexical",
    "Лексика:морф.": "OTHER:lexical_morph",
    "REPLACE": "OTHER:lexical",
    "WO": "OTHER:word_order",
    # GERA lexical types (L: prefix)
    "L:REP": "OTHER:lexical",
    "L:OTHER": "OTHER:lexical",
    "L:MORPH": "OTHER:lexical_morph",
    "L:CONSTR": "OTHER:lexical",  # Construction errors
    "L:STYLE": "OTHER:lexical",
    "L:COLLOC": "OTHER:lexical",  # Collocation errors
    # =========================================================================
    # FUNCTION WORDS → OTHER:preposition/conjunction/pronoun
    # =========================================================================
    "Предлог": "OTHER:preposition",
    "Союз": "OTHER:conjunction",
    "Местоимение": "OTHER:pronoun",
    "PREP": "OTHER:preposition",
    "G:PREP": "OTHER:preposition",
    "G:CONJ": "OTHER:conjunction",
    # =========================================================================
    # PUNCTUATION → PUNCT
    # =========================================================================
    "Пунктуация": "PUNCT",
    "PUNCT": "PUNCT",
    "P:PUNCT": "PUNCT",
    # =========================================================================
    # AGREEMENT → MORPH:agreement_*
    # =========================================================================
    "Согласование:Прил-Сущ:Падеж": "MORPH:agreement_adj_noun",
    "Согласование:Прил-Сущ:Число": "MORPH:agreement_adj_noun",
    "Согласование:Прил-Сущ:Род": "MORPH:agreement_adj_noun",
    "Согласование:Подл-Сказ:Число": "MORPH:agreement_subj_verb",
    "Согласование:Подл-Сказ:Лицо": "MORPH:agreement_subj_verb",
    "G:AGREEMENT": "MORPH:agreement_other",
    # =========================================================================
    # OTHER/UNKNOWN
    # =========================================================================
    "Другое": "OTHER:other",
    "OTHER": "OTHER:other",
    "UNK": "OTHER:unknown",
    "SYNTAX": "OTHER:syntax",
    "SEMANTICS": "OTHER:semantics",
}


@dataclass
class DistributionStats:
    """Statistics from analyzing a benchmark dataset."""

    source: str
    total_sentences: int = 0
    total_errors: int = 0
    error_counts: Counter = field(default_factory=Counter)
    category_counts: Counter = field(default_factory=Counter)
    unmapped_types: Counter = field(default_factory=Counter)

    @property
    def errors_per_sentence(self) -> float:
        """Average errors per sentence."""
        if self.total_sentences == 0:
            return 0.0
        return self.total_errors / self.total_sentences

    def get_distribution(self, normalize: bool = True) -> dict[str, float]:
        """Get error type distribution.

        Args:
            normalize: If True, return percentages (sum to 1.0)

        Returns:
            Dict mapping error types to counts or percentages
        """
        if not normalize:
            return dict(self.error_counts)

        total = sum(self.error_counts.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in self.error_counts.items()}

    def get_category_distribution(self, normalize: bool = True) -> dict[str, float]:
        """Get category-level distribution (SPELL, MORPH, PUNCT, OTHER)."""
        if not normalize:
            return dict(self.category_counts)

        total = sum(self.category_counts.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in self.category_counts.items()}

    def get_synterr_weights(
        self, include_unimplemented: bool = False
    ) -> dict[str, float]:
        """Convert to synterr error handler weights.

        Maps benchmark error types to synterr handler names.

        Args:
            include_unimplemented: Include handlers not yet in synterr (for planning)
        """
        # Mapping from mapped category to synterr handler name
        handler_mapping = {
            # Implemented handlers
            "SPELL": "spelling",
            "MORPH:noun_case": "noun_case",
            "MORPH:noun_number": "noun_number",
            "MORPH:adj_case": "adj_case",
            "MORPH:adj_number": "adj_number",
            "MORPH:adj_gender": "adj_gender",
            "MORPH:verb_tense": "verb_tense",
            "MORPH:verb_person_number": "verb_person_number",
        }

        if include_unimplemented:
            handler_mapping.update(
                {
                    "MORPH:verb_aspect": "verb_aspect",
                    "MORPH:verb_voice": "verb_voice",
                    "OTHER:insert": "insert",
                    "OTHER:delete": "delete",
                    "OTHER:preposition": "preposition",
                    "OTHER:conjunction": "conjunction",
                    "OTHER:pronoun": "pronoun",
                    "OTHER:lexical": "lexical",
                    "PUNCT": "punctuation",
                }
            )

        # Use category_counts (mapped categories), not error_counts (raw types)
        total = sum(self.category_counts.values())
        if total == 0:
            return {}

        weights = {}
        for category, handler_name in handler_mapping.items():
            if category in self.category_counts:
                weights[handler_name] = self.category_counts[category] / total

        # Normalize weights to sum to 1.0
        weight_total = sum(weights.values())
        if weight_total > 0:
            weights = {k: v / weight_total for k, v in weights.items()}

        return weights


def analyze_m2_file(path: str | Path) -> DistributionStats:
    """Analyze an M2 file to extract error distribution.

    Args:
        path: Path to M2 format file

    Returns:
        DistributionStats with error counts and distribution
    """
    path = Path(path)
    stats = DistributionStats(source=path.name)

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line.startswith("S "):
                # Source sentence
                stats.total_sentences += 1

            elif line.startswith("A "):
                # Annotation line
                match = M2_ANNOTATION_PATTERN.match(line)
                if match:
                    error_type = match.group(3).strip()

                    # Skip no-op annotations
                    if error_type in ("noop", "-NONE-", ""):
                        continue

                    stats.total_errors += 1
                    stats.error_counts[error_type] += 1

                    # Map to category
                    category = ERROR_TYPE_TO_CATEGORY.get(error_type)
                    if category:
                        stats.category_counts[category] += 1
                        # Also count top-level category
                        top_category = category.split(":")[0]
                        if top_category != category:
                            stats.category_counts[top_category] += 1
                    else:
                        stats.unmapped_types[error_type] += 1

    return stats


def aggregate_distributions(
    stats_list: Iterable[DistributionStats],
) -> DistributionStats:
    """Aggregate multiple distribution stats into one.

    Args:
        stats_list: List of DistributionStats to combine

    Returns:
        Combined DistributionStats
    """
    combined = DistributionStats(source="combined")

    for stats in stats_list:
        combined.total_sentences += stats.total_sentences
        combined.total_errors += stats.total_errors
        combined.error_counts.update(stats.error_counts)
        combined.category_counts.update(stats.category_counts)
        combined.unmapped_types.update(stats.unmapped_types)

    return combined


def print_distribution_report(stats: DistributionStats) -> None:
    """Print a formatted distribution report."""
    print(f"\n{'=' * 60}")
    print(f"Distribution Analysis: {stats.source}")
    print(f"{'=' * 60}")
    print(f"Total sentences: {stats.total_sentences:,}")
    print(f"Total errors: {stats.total_errors:,}")
    print(f"Errors per sentence: {stats.errors_per_sentence:.2f}")

    print(f"\n{'─' * 60}")
    print("Error Type Distribution:")
    print(f"{'─' * 60}")

    dist = stats.get_distribution(normalize=True)
    for error_type, pct in sorted(dist.items(), key=lambda x: -x[1])[:20]:
        count = stats.error_counts[error_type]
        bar = "█" * int(pct * 40)
        print(f"  {error_type:30s} {count:5d} ({pct:5.1%}) {bar}")

    print(f"\n{'─' * 60}")
    print("Category Distribution:")
    print(f"{'─' * 60}")

    cat_dist = stats.get_category_distribution(normalize=True)
    for category, pct in sorted(cat_dist.items(), key=lambda x: -x[1]):
        if ":" not in category:  # Top-level only
            count = stats.category_counts[category]
            bar = "█" * int(pct * 40)
            print(f"  {category:15s} {count:5d} ({pct:5.1%}) {bar}")

    if stats.unmapped_types:
        print(f"\n{'─' * 60}")
        print(f"Unmapped types ({len(stats.unmapped_types)}):")
        for t, c in stats.unmapped_types.most_common(10):
            print(f"  {t}: {c}")

    print(f"\n{'─' * 60}")
    print("Synterr weights (implemented handlers only):")
    print(f"{'─' * 60}")
    weights = stats.get_synterr_weights()
    for handler, weight in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"  {handler:25s} {weight:.3f}")
