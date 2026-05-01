"""LoRuGEC rule mapping — shared between CLI and scripts.

Maps each of the 48 LoRuGEC benchmark rules to a synterr handler + subtype,
with optional word filters for conjunction-specific rules.
"""

from __future__ import annotations

from pathlib import Path

# LoRuGEC rule name → (handler_name, subtype) or (handler_name, subtype, word_filter)
# word_filter: only accept results where original or corrupted contains this word
LORUGEC_RULES: dict[str, tuple[str, ...]] = {
    # === Spelling (24 rules) ===
    #
    # BIDIRECTIONAL rules: LoRuGEC tests BOTH directions for all split/merge rules.
    # [split] = handler splits solid→separate, src has separate form, model learns to merge
    # [merge] = handler merges separate→solid, src has solid form, model learns to split
    # Use --balance-directions to cap the larger direction to match the smaller.
    #
    # не/ни — both attachment (не+word→неword) and detachment (неword→не word)
    'Правописание "не" с существительными [attach]': (
        "function_spelling",
        "ne_attachment",
    ),
    'Правописание "не" с существительными [detach]': (
        "function_spelling",
        "ne_detachment",
    ),
    'Правописание "не" с прилагательными [attach]': (
        "function_spelling",
        "ne_attachment",
    ),
    'Правописание "не" с прилагательными [detach]': (
        "function_spelling",
        "ne_detachment",
    ),
    'Правописание "не" с глаголами [attach]': ("function_spelling", "ne_attachment"),
    'Правописание "не" с глаголами [detach]': ("function_spelling", "ne_detachment"),
    'Правописание "не" с причастиями [attach]': ("function_spelling", "ne_attachment"),
    'Правописание "не" с причастиями [detach]': ("function_spelling", "ne_detachment"),
    # Conjunctions — split + merge per word
    'Правописание "чтобы" [split]': ("function_spelling", "conjunction_split", "чтобы"),
    'Правописание "чтобы" [merge]': ("function_spelling", "conjunction_merge", "чтобы"),
    'Правописание "причем" [split]': (
        "function_spelling",
        "conjunction_split",
        "причем",
    ),
    'Правописание "причем" [merge]': (
        "function_spelling",
        "conjunction_merge",
        "причем",
    ),
    'Правописание "оттого" [split]': (
        "function_spelling",
        "conjunction_split",
        "оттого",
    ),
    'Правописание "оттого" [merge]': (
        "function_spelling",
        "conjunction_merge",
        "оттого",
    ),
    'Правописание "зато" [split]': ("function_spelling", "conjunction_split", "зато"),
    'Правописание "зато" [merge]': ("function_spelling", "conjunction_merge", "зато"),
    'Правописание "также" [split]': ("function_spelling", "conjunction_split", "также"),
    'Правописание "также" [merge]': ("function_spelling", "conjunction_merge", "также"),
    # -таки — both directions (add hyphen, remove hyphen)
    "Правописание частицы -таки [split]": ("function_spelling", "taki_hyphen"),
    "Правописание частицы -таки [merge]": ("function_spelling", "taki_hyphen"),
    # Orthographic (character-level, not directional)
    "Правописание приставок пре- и при-": ("orthographic_spelling", "pre_pri"),
    'Гласные "ы" и "и" после приставок': ("orthographic_spelling", "y_i_after_prefix"),
    "Правописание суффиксов -еньк, -оньк в существительных. ": (
        "orthographic_spelling",
        "suffix_enk_onk",
    ),
    "Правописание суффиксов −инск, −енск в прилагательных": (
        "orthographic_spelling",
        "suffix_insk_ensk",
    ),
    "Правописание суффиксов -иц, -ец в существительных среднего рода": (
        "orthographic_spelling",
        "suffix_its_ets",
    ),
    "Правописание суффиксов −ек, −ик": ("orthographic_spelling", "suffix_ek_ik"),
    "Правописание гласных в суффиксах причастий": (
        "orthographic_spelling",
        "participle_suffix",
    ),
    'Гласные после "ц"': ("orthographic_spelling", "vowel_after_ts"),
    "Гласные после шипящих": ("orthographic_spelling", "vowel_after_sibilant"),
    '"н" и "нн" в суффиксах прилагательных': ("orthographic_spelling", "nn_suffix"),
    'Правописание разделительных "ъ" и "ь"': ("spelling", "soft_sign"),
    # Compounds
    "Правописание числительного пол-": ("compound_spelling", "pol_spelling"),
    "Дефис в составе письменных эквивалентов сложных слов": (
        "compound_spelling",
        "num_dash",
    ),
    "Правописание сложных прилагательных": ("compound_spelling", "compound_adj"),
    # Adverbs — both directions
    "Наречия [split]": ("adverb_spelling", "adverb_solid_to_separate"),
    "Наречия [merge]": ("adverb_spelling", "adverb_separate_to_solid"),
    # === Grammar (4 rules) ===
    "Нарушение норм управления": ("adj_case", "adj_case"),
    "Согласование причастий с определяемым словом": ("adj_case", "adj_case"),
    'Склонение числительных "полтора", "полторы", "полтораста"': (
        "numeral_declension",
        "numeral_poltora",
    ),
    "Склонение количественных числительных": (
        "numeral_declension",
        "numeral_declension",
    ),
    # === Semantics (2 rules) ===
    "Плеоназмы": ("pleonasm", "pleonasm"),
    "Лексическая сочетаемость слов": ("collocation", "collocation"),
    # === Punctuation (18 rules) ===
    "Запятая внутри выражений фразеологического характера": (
        "comma_insert",
        "comma_in_set_phrase",
    ),
    "Пунктуация в цельных по смыслу (неразложимых) сочетаниях": (
        "comma_insert",
        "comma_in_indivisible",
    ),
    "Знаки препинания в предложениях с однородными членами: пары": (
        "comma_delete",
        "comma_homogeneous",
    ),
    "Обособление деепричастий после союзов": ("comma_pair_delete", "pair_gerund"),
    "Запятая между частями СПП с общей частью": ("comma_delete", "comma_subordinate"),
    'Запятая перед союзом "как": 1': ("comma_insert", "comma_before_kak"),
    "Запятая между однородными придаточными": ("comma_delete", "comma_subordinate"),
    "Обособление согласованных определений, относящихся к личному местоимению": (
        "comma_pair_delete",
        "pair_participle",
    ),
    "Обособление согласованных определений, оторванных от определяемого слова": (
        "comma_pair_delete",
        "pair_participle",
    ),
    'Запятая перед союзом "как": 2': ("comma_insert", "comma_before_kak"),
    'Запятая перед союзом "как": 3': ("comma_insert", "comma_before_kak"),
    "Пунктуация при повторяющихся союзах": ("comma_delete", "comma_homogeneous"),
    "Пунктуация при вводных словах и конструкциях": (
        "comma_pair_delete",
        "pair_parenthetical",
    ),
    "Тире при приложении": ("dash_delete", "dash_other"),
    "Тире между подлежащим и сказуемым": ("dash_delete", "dash_subj_pred"),
    "Тире в бессоюзных предложениях": ("dash_delete", "dash_asyndetic"),
    "Запятая на стыке двух союзов": ("comma_insert", "comma_between_conjunctions"),
}


def extract_subtype(error_type: str, handler_name: str) -> str | None:
    """Extract the subtype from an error_type string."""
    if not error_type:
        return None
    prefix = handler_name + "_"
    if error_type.startswith(prefix):
        return error_type[len(prefix) :]
    return error_type


def get_lorugec_distribution() -> dict[str, int]:
    """Read LoRuGEC rule counts from the Excel file, with fallback."""
    try:
        from collections import Counter

        import openpyxl

        # Try common locations
        for base in [Path.cwd(), Path(__file__).parent.parent.parent]:
            xlsx = base / "gector" / "data" / "lorugec-data" / "LORuGEC.xlsx"
            if xlsx.exists():
                wb = openpyxl.load_workbook(xlsx, read_only=True)
                ws = wb["Sheet1"]
                counts = Counter()
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if row[0]:
                        counts[row[0]] += 1
                return dict(counts)
    except Exception:
        pass
    # Fallback: uniform 20 per rule
    return {rule: 20 for rule in LORUGEC_RULES}
