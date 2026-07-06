"""Tests for semantic handlers (pleonasm, collocation).

These are unit-level using hand-built AnalyzedToken lists, but the inflection
paths exercise the real pymorphy3 analyzer, so they catch the citation-form
bugs found in the 2026-05-27 audit.
"""

import pymorphy3
import pytest

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.semantics import (
    CollocationHandler,
    PleonasmHandler,
)

_morph = pymorphy3.MorphAnalyzer()


def _tok(text, pos="NOUN", lemma=None, idx=0, head_idx=None, dep_rel=None):
    """Build a token with a real pymorphy parse in extra (matches backend)."""
    parses = _morph.parse(text)
    parse = parses[0] if parses else None
    return AnalyzedToken(
        text=text,
        lemma=lemma or (parse.normal_form if parse else text.lower()),
        pos=pos,
        features={},
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
        extra={"pymorphy_parse": parse},
    )


class TestPleonasmHandler:
    handler = PleonasmHandler()

    def test_protocol(self):
        assert self.handler.name == "pleonasm"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is True

    def test_inserts_and_agrees(self):
        # "прочитал автобиографию" → insert "свою" agreeing in case (accs/femn)
        tokens = [
            _tok("прочитал", pos="VERB", idx=0),
            _tok("автобиографию", lemma="автобиография", idx=1),
        ]
        sentence = ["прочитал", "автобиографию"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        # Inserted modifier should agree (свою), not be the citation form своя
        assert "свою" in sentence
        assert sentence == ["прочитал", "свою", "автобиографию"]

    def test_skips_when_redundant_already_present_inflected(self):
        # "написал свою автобиографию" — "свою" (lemma свой) already there.
        # The data's redundant form is "своя"; lemma-level guard must catch it.
        tokens = [
            _tok("написал", pos="VERB", idx=0),
            _tok("свою", pos="NPRO", lemma="свой", idx=1),
            _tok("автобиографию", lemma="автобиография", idx=2),
        ]
        assert self.handler.can_apply(tokens, 2) is False
        sentence = ["написал", "свою", "автобиографию"]
        assert self.handler.apply(tokens, sentence, 2, set()) is None

    def test_no_apply_for_unknown_word(self):
        tokens = [_tok("стол", idx=0)]
        assert self.handler.can_apply(tokens, 0) is False

    # 2026-06 audit: entries whose insertion yields ordinary correct Russian
    # ("ранним утром", "скрытый потенциал", "тёмный силуэт", "полная
    # гарантия") were removed — none appear in Rozental §141, and the output
    # was a non-error labeled with a $DELETE fix.
    @pytest.mark.parametrize(
        ("text", "lemma"),
        [
            ("Утром", "утро"),
            ("потенциал", "потенциал"),
            ("силуэтом", "силуэт"),
            ("гарантия", "гарантия"),
        ],
    )
    def test_nonerror_entries_removed(self, text, lemma):
        tokens = [_tok(text, lemma=lemma, idx=0)]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = [text]
        assert self.handler.apply(tokens, sentence, 0, set()) is None
        assert sentence == [text]

    # 2026-06 audit: Rozental §141 explicitly permits "патриот своей родины"
    # in modern usage; пантомима+молча yielded ordinary adverbial usage
    # ("показал молча пантомиму"); диалог+"между двумя" left a dangling
    # fragment ("Диалог между двумя затянулся"). All three entries removed.
    @pytest.mark.parametrize(
        ("text", "lemma"),
        [
            ("патриот", "патриот"),
            ("пантомиму", "пантомима"),
            ("Диалог", "диалог"),
        ],
    )
    def test_audit_2026_06_entries_removed(self, text, lemma):
        tokens = [_tok(text, lemma=lemma, idx=0)]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = [text]
        assert self.handler.apply(tokens, sentence, 0, set()) is None
        assert sentence == [text]

    def test_sentence_initial_insert_transfers_capitalization(self):
        # "Ветеран выступил" → "Старый ветеран выступил", not "старый Ветеран"
        tokens = [
            _tok("Ветеран", lemma="ветеран", idx=0),
            _tok("выступил", pos="VERB", lemma="выступить", idx=1),
        ]
        sentence = ["Ветеран", "выступил"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence == ["Старый", "ветеран", "выступил"]
        assert result.corrupted == "Старый"

    def test_adjective_core_agreement(self):
        # "на конечной остановке" → "на окончательной конечной остановке",
        # not the citation form "окончательный" (2026-06 audit).
        tokens = [
            _tok("на", pos="ADP", lemma="на", idx=0),
            _tok("конечной", pos="ADJ", lemma="конечный", idx=1),
            _tok("остановке", lemma="остановка", idx=2),
        ]
        sentence = ["на", "конечной", "остановке"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert sentence == ["на", "окончательной", "конечной", "остановке"]

    def test_verb_core_agreement_past_feminine(self):
        # "команда лидировала" → "первой лидировала" (instrumental kept,
        # gender/number agreed with the past-tense verb), not "первым".
        tokens = [
            _tok("команда", lemma="команда", idx=0),
            _tok("лидировала", pos="VERB", lemma="лидировать", idx=1),
        ]
        sentence = ["команда", "лидировала"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert sentence == ["команда", "первой", "лидировала"]

    def test_verb_core_skipped_when_agreement_unestablishable(self):
        # Present-tense verbs carry no gender — inserting "первым" against
        # e.g. a feminine subject would be agreement garbage, so skip.
        tokens = [
            _tok("команда", lemma="команда", idx=0),
            _tok("лидирует", pos="VERB", lemma="лидировать", idx=1),
        ]
        sentence = ["команда", "лидирует"]
        assert self.handler.apply(tokens, sentence, 1, set()) is None
        assert sentence == ["команда", "лидирует"]

    def test_redundant_guard_scans_whole_np(self):
        # "свою очень подробную автобиографию" — possessive is 3 tokens away
        # but still in the NP; the old ±2 window missed it and produced
        # "свою очень подробную свою автобиографию" (2026-06 audit).
        tokens = [
            _tok("написал", pos="VERB", lemma="написать", idx=0),
            _tok("свою", pos="DET", lemma="свой", idx=1),
            _tok("очень", pos="ADV", lemma="очень", idx=2),
            _tok("подробную", pos="ADJ", lemma="подробный", idx=3),
            _tok("автобиографию", lemma="автобиография", idx=4),
        ]
        assert self.handler.can_apply(tokens, 4) is False
        sentence = ["написал", "свою", "очень", "подробную", "автобиографию"]
        assert self.handler.apply(tokens, sentence, 4, set()) is None

    def test_redundant_guard_does_not_cross_clause_boundary(self):
        # "вернул свою книгу и прочитал автобиографию": "свою" sits in a
        # different clause (behind the verb "прочитал"), so insertion before
        # "автобиографию" is still a clean pleonasm and must not be blocked.
        tokens = [
            _tok("вернул", pos="VERB", lemma="вернуть", idx=0),
            _tok("свою", pos="DET", lemma="свой", idx=1),
            _tok("книгу", lemma="книга", idx=2),
            _tok("и", pos="CCONJ", lemma="и", idx=3),
            _tok("прочитал", pos="VERB", lemma="прочитать", idx=4),
            _tok("автобиографию", lemma="автобиография", idx=5),
        ]
        assert self.handler.can_apply(tokens, 5) is True

    def test_minuta_vremeni_backfill_fires(self):
        # §141: "беречь каждую минуту времени" — invariant genitive attribute,
        # safe to insert after any case form of минута.
        tokens = [
            _tok("каждую", pos="ADJF", lemma="каждый", idx=0),
            _tok("минуту", lemma="минута", idx=1),
        ]
        assert self.handler.can_apply(tokens, 1) is True
        sentence = ["каждую", "минуту"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert sentence == ["каждую", "минуту", "времени"]


class TestCollocationHandler:
    handler = CollocationHandler()

    def test_protocol(self):
        assert self.handler.name == "collocation"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def test_replacement_is_inflected_not_citation(self):
        # "принял решение" → "сделал решение" (finite past), NOT "сделать"
        tokens = [
            _tok("принял", pos="VERB", lemma="принять", idx=0),
            _tok("решение", lemma="решение", idx=1),
        ]
        if not self.handler.can_apply(tokens, 0):
            pytest.skip("collocation lexicon does not contain принять/решение pair")
        sentence = ["принял", "решение"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        # Must not be the bare infinitive
        assert sentence[0] != "сделать"
        # Should be a past-tense finite form
        assert sentence[0].endswith("л") or sentence[0].endswith("ла")

    def test_inflected_collocate_entry_fires_oderzhat(self):
        # Lexicon stores the accusative collocate "победу"; the noun token's
        # lemma is "победа". Load-time lemmatization must make these match so
        # this previously-dead verb fires.
        tokens = [
            _tok("одержала", pos="VERB", lemma="одержать", idx=0),
            _tok("победу", lemma="победа", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        sentence = ["одержала", "победу"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] != "одержала"
        # Inflected to match the past feminine original, not a bare infinitive.
        assert not sentence[0].endswith("ть")

    def test_inflected_collocate_entry_fires_vyzvat(self):
        # "вызвало реакцию" — collocate stored as accusative "реакцию".
        tokens = [
            _tok("вызвало", pos="VERB", lemma="вызвать", idx=0),
            _tok("реакцию", lemma="реакция", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        sentence = ["вызвало", "реакцию"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] != "вызвало"
        assert not sentence[0].endswith("ть")

    # 2026-06 audit: entries whose "wrong" replacement is dictionary-attested
    # correct Russian (кинуть взгляд, искупить вину, причинить вред,
    # поставить рекорд, приобрести уважение) were removed — none are listed
    # as errors in Rozental §143 or any normative source.
    @pytest.mark.parametrize(
        ("verb", "verb_lemma", "noun", "noun_lemma"),
        [
            ("бросил", "бросить", "взгляд", "взгляд"),
            ("загладить", "загладить", "вину", "вина"),
            ("заслужил", "заслужить", "уважение", "уважение"),
        ],
    )
    def test_nonerror_entries_removed(self, verb, verb_lemma, noun, noun_lemma):
        tokens = [
            _tok(verb, pos="VERB", lemma=verb_lemma, idx=0),
            _tok(noun, lemma=noun_lemma, idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = [verb, noun]
        assert self.handler.apply(tokens, sentence, 0, set()) is None

    def test_nanesti_vred_prichinit_removed(self):
        # "причинить вред" is standard legal terminology (ГК РФ гл. 59); the
        # нанести key keeps only the genuine error оказать/ущерб.
        tokens = [
            _tok("нанесла", pos="VERB", lemma="нанести", idx=0),
            _tok("вред", lemma="вред", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_ustanovit_rekord_never_postavit(self):
        # установить/рекорд still fires (завоевать), but the поставить entry
        # is gone — "поставить рекорд" is dictionary-attested under РЕКОРД.
        import random

        tokens = [
            _tok("установил", pos="VERB", lemma="установить", idx=0),
            _tok("рекорд", lemma="рекорд", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        for seed in range(20):
            sentence = ["установил", "рекорд"]
            result = self.handler.apply(tokens, sentence, 0, set(), random.Random(seed))
            assert result is not None
            assert not sentence[0].startswith("постав")

    def test_vysokaya_cena_entry_removed(self):
        # высокий→дорогой dropped entirely: "дорогой ценой" is a normative
        # idiom, and the homograph parse produced non-words ("по дороги цене").
        tokens = [
            _tok("по", pos="PREP", lemma="по", idx=0),
            _tok("высокой", pos="ADJF", lemma="высокий", idx=1),
            _tok("цене", lemma="цена", idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_inflect_to_match_skips_homograph_noun_parse(self):
        # parse("дорогой")[0] is NOUN дорога sing,ablt; same_pos must skip it
        # and pick the adjective lexeme.
        from synterr.languages.russian.errors.semantics import _inflect_to_match

        adj_parse = next(p for p in _morph.parse("высокой") if p.tag.POS == "ADJF")
        result = _inflect_to_match("дорогой", adj_parse, same_pos=True)
        # Any feminine singular oblique form of the adjective is "дорогой";
        # the noun homograph would have given "дороги"/"дороге".
        assert result == "дорогой"

    def test_adjective_entry_inflects_as_adjective(self):
        # низкий→дешёвый must agree with the noun phrase, not collapse into a
        # homograph: "по низкой цене" → "по дешёвой цене".
        tokens = [
            _tok("по", pos="PREP", lemma="по", idx=0),
            _tok("низкой", pos="ADJF", lemma="низкий", idx=1),
            _tok("цене", lemma="цена", idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is True
        sentence = ["по", "низкой", "цене"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert sentence[1] == "дешёвой"

    def test_collocate_inside_participial_phrase_not_corrupted(self):
        # 2026-06 audit: "Он принял гостей, обсуждавших решение" —
        # "решение" depends on "обсуждавших", not on "принял", so the
        # принять→сделать corruption must not fire on lemma co-occurrence.
        tokens = [
            _tok("Он", pos="PRON", lemma="он", idx=0, head_idx=1, dep_rel="nsubj"),
            _tok(
                "принял",
                pos="VERB",
                lemma="принять",
                idx=1,
                head_idx=-1,
                dep_rel="root",
            ),
            _tok("гостей", lemma="гость", idx=2, head_idx=1, dep_rel="obj"),
            _tok(",", pos="PUNCT", lemma=",", idx=3, head_idx=4, dep_rel="punct"),
            _tok(
                "обсуждавших",
                pos="VERB",
                lemma="обсуждать",
                idx=4,
                head_idx=2,
                dep_rel="acl",
            ),
            _tok("решение", lemma="решение", idx=5, head_idx=4, dep_rel="obj"),
            _tok(".", pos="PUNCT", lemma=".", idx=6, head_idx=1, dep_rel="punct"),
        ]
        assert self.handler.can_apply(tokens, 1) is False
        sentence = [t.text for t in tokens]
        assert self.handler.apply(tokens, sentence, 1, set()) is None
        assert sentence[1] == "принял"

    def test_dep_linked_collocate_fires(self):
        # With dep info, a non-adjacent but directly linked object still
        # triggers: "принял важное решение" (решение ← obj ← принял).
        tokens = [
            _tok(
                "принял",
                pos="VERB",
                lemma="принять",
                idx=0,
                head_idx=-1,
                dep_rel="root",
            ),
            _tok(
                "важное", pos="ADJ", lemma="важный", idx=1, head_idx=2, dep_rel="amod"
            ),
            _tok("решение", lemma="решение", idx=2, head_idx=0, dep_rel="obj"),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        sentence = ["принял", "важное", "решение"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] != "принял"

    def test_without_dep_info_requires_adjacency(self):
        # Without depparse there is no way to verify the object relation,
        # so only adjacent verb+collocate pairs may fire.
        tokens = [
            _tok("принял", pos="VERB", lemma="принять", idx=0),
            _tok("важное", pos="ADJ", lemma="важный", idx=1),
            _tok("решение", lemma="решение", idx=2),
        ]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = ["принял", "важное", "решение"]
        assert self.handler.apply(tokens, sentence, 0, set()) is None

    def test_rozental_143_backfill_fires(self):
        # §143: "производить воздействие (вместо оказывать воздействие)".
        tokens = [
            _tok("оказывает", pos="VERB", lemma="оказывать", idx=0),
            _tok("воздействие", lemma="воздействие", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        sentence = ["оказывает", "воздействие"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] == "производит"
