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
    # не/ни
    'Правописание частицы "не" с существительными': ("function_spelling", "ne_attachment"),
    'Правописание "не" с прилагательными': ("function_spelling", "ne_attachment"),
    'Правописание "не" с глаголами': ("function_spelling", "ne_detachment"),
    'Правописание частицы "не" с причастиями': ("function_spelling", "ne_attachment"),
    # Conjunctions — both split (solid→separate) and merge (separate→solid)
    # Each rule needs both directions so the model learns bidirectionally
    'Правописание "чтобы"': ("function_spelling", ("conjunction_split", "conjunction_merge"), "чтобы"),
    'Правописание "причем" и "притом"': ("function_spelling", ("conjunction_split", "conjunction_merge"), "причем"),
    'Правописание "оттого"': ("function_spelling", ("conjunction_split", "conjunction_merge"), "оттого"),
    'Правописание "зато"': ("function_spelling", ("conjunction_split", "conjunction_merge"), "зато"),
    'Правописание "также"': ("function_spelling", ("conjunction_split", "conjunction_merge"), "также"),
    # -таки
    "Правописание частицы -таки": ("function_spelling", "taki_hyphen"),
    # Orthographic
    'Правописание приставок пре- и при-': ("orthographic_spelling", "pre_pri"),
    'Гласные "ы" и "и" после приставок': ("orthographic_spelling", "y_i_after_prefix"),
    'Правописание суффиксов -еньк, -оньк в существительных. ': ("orthographic_spelling", "suffix_enk_onk"),
    "Правописание суффиксов −инск, −енск в прилагательных": ("orthographic_spelling", "suffix_insk_ensk"),
    "Правописание суффиксов -иц, -ец в существительных среднего рода": ("orthographic_spelling", "suffix_its_ets"),
    "Правописание суффиксов −ек, −ик": ("orthographic_spelling", "suffix_ek_ik"),
    "Правописание гласных в суффиксах причастий": ("orthographic_spelling", "participle_suffix"),
    'Гласные после "ц"': ("orthographic_spelling", "vowel_after_ts"),
    "Гласные после шипящих": ("orthographic_spelling", "vowel_after_sibilant"),
    '"н" и "нн" в суффиксах прилагательных': ("orthographic_spelling", "nn_suffix"),
    'Правописание разделительных "ъ" и "ь"': ("spelling", "soft_sign"),
    # Compounds
    "Правописание числительного пол-": ("compound_spelling", "pol_spelling"),
    "Дефис в составе письменных эквивалентов сложных слов": ("compound_spelling", "num_dash"),
    "Правописание сложных прилагательных": ("compound_spelling", "compound_adj"),
    # Adverbs
    "Слитное, раздельное и дефисное написание наречий": ("adverb_spelling", "adverb_solid_to_separate"),

    # === Grammar (4 rules) ===
    "Нарушение норм управления": ("adj_case", "adj_case"),
    "Согласование причастий с определяемым словом": ("adj_case", "adj_case"),
    'Склонение числительных "полтора", "полторы", "полтораста"': ("numeral_declension", "numeral_poltora"),
    "Склонение количественных числительных": ("numeral_declension", "numeral_declension"),

    # === Semantics (2 rules) ===
    "Плеоназмы": ("pleonasm", "pleonasm"),
    "Лексическая сочетаемость слов": ("collocation", "collocation"),

    # === Punctuation (18 rules) ===
    "Запятая внутри выражений фразеологического характера": ("comma_insert", "comma_in_set_phrase"),
    "Пунктуация в цельных по смыслу (неразложимых) сочетаниях": ("comma_insert", "comma_in_indivisible"),
    "Знаки препинания в предложениях с однородными членами: пары": ("comma_delete", "comma_homogeneous"),
    "Обособление деепричастий после союзов": ("comma_pair_delete", "pair_gerund"),
    "Запятая между частями СПП с общей частью": ("comma_delete", "comma_subordinate"),
    'Запятая перед союзом "как": 1': ("comma_insert", "comma_before_kak"),
    "Запятая между однородными придаточными": ("comma_delete", "comma_subordinate"),
    "Обособление согласованных определений, относящихся к личному местоимению": ("comma_pair_delete", "pair_participle"),
    "Обособление согласованных определений, оторванных от определяемого слова": ("comma_pair_delete", "pair_participle"),
    'Запятая перед союзом "как": 2': ("comma_insert", "comma_before_kak"),
    'Запятая перед союзом "как": 3': ("comma_insert", "comma_before_kak"),
    "Пунктуация при повторяющихся союзах": ("comma_delete", "comma_homogeneous"),
    "Пунктуация при вводных словах и конструкциях": ("comma_pair_delete", "pair_parenthetical"),
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
        return error_type[len(prefix):]
    return error_type


def get_lorugec_distribution() -> dict[str, int]:
    """Read LoRuGEC rule counts from the Excel file, with fallback."""
    try:
        import openpyxl
        from collections import Counter

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
