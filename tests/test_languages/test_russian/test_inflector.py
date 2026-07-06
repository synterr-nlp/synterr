"""Tests for inflector helpers."""

import pymorphy3

from synterr.languages.russian.inflector import inflect_word, match_capitalization


class TestInflectWordYoNormalization:
    def test_yo_stripped_when_original_uses_e(self):
        morph = pymorphy3.MorphAnalyzer()
        parse = next(p for p in morph.parse("сушеной") if "ADJF" in p.tag)
        word = inflect_word(parse, {"masc", "sing", "ablt"}, "сушеной")
        assert word is not None
        assert "ё" not in word

    def test_yo_kept_when_original_has_yo(self):
        morph = pymorphy3.MorphAnalyzer()
        parse = next(p for p in morph.parse("сушёной") if "ADJF" in p.tag)
        word = inflect_word(parse, {"masc", "sing", "ablt"}, "сушёной")
        assert word == "сушёным"


class TestMatchCapitalization:
    def test_lowercase_preserved(self):
        assert match_capitalization("в", "на") == "на"

    def test_titlecase_transferred(self):
        assert match_capitalization("Мама", "рама") == "Рама"

    def test_allcaps_transferred(self):
        assert match_capitalization("ВЕСЬ", "целый") == "ЦЕЛЫЙ"

    def test_single_capital_letter_is_titlecase_not_allcaps(self):
        # Sentence-initial "В" must become "На", not "НА"
        assert match_capitalization("В", "на") == "На"

    def test_single_letter_to_single_letter(self):
        assert match_capitalization("В", "с") == "С"

    def test_empty_strings(self):
        assert match_capitalization("", "на") == "на"
        assert match_capitalization("В", "") == ""
