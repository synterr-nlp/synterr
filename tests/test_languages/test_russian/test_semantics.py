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

    def test_sentence_initial_capitalized_core_skipped(self):
        # Audit C2 (2026-07): the old behavior capitalized the inserted word
        # and demoted the core to lowercase ("Ветеран выступил" → "Старый
        # ветеран выступил"), but only a single $DELETE tag is emitted (on
        # "Старый"). Reconstructing from that one edit yields "ветеран
        # выступил" — the core's original capital "Ветеран" is permanently
        # lost. Precision-first fix: skip rather than emit an uncorrectable
        # corruption (mirrors DoubleComparativeHandler's
        # `if word[:1].isupper(): return None`).
        tokens = [
            _tok("Ветеран", lemma="ветеран", idx=0),
            _tok("выступил", pos="VERB", lemma="выступить", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = ["Ветеран", "выступил"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is None
        assert sentence == ["Ветеран", "выступил"]

    def test_sentence_initial_lowercase_core_still_fires(self):
        # A lowercase sentence-initial core (e.g. a fragment) has nothing to
        # lose from a single $DELETE, so it must still fire.
        tokens = [
            _tok("ветеран", lemma="ветеран", idx=0),
            _tok("выступил", pos="VERB", lemma="выступить", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        sentence = ["ветеран", "выступил"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence == ["старый", "ветеран", "выступил"]

    def test_capitalized_core_mid_sentence_still_fires(self):
        # The C2 guard is specific to idx == 0 (sentence-initial); a
        # capitalized core elsewhere in the sentence (e.g. after a colon or
        # in a subordinate clause) is unaffected.
        tokens = [
            _tok("сказал", pos="VERB", lemma="сказать", idx=0),
            _tok(":", pos="PUNCT", lemma=":", idx=1),
            _tok("Ветеран", lemma="ветеран", idx=2),
            _tok("выступил", pos="VERB", lemma="выступить", idx=3),
        ]
        assert self.handler.can_apply(tokens, 2) is True
        sentence = ["сказал", ":", "Ветеран", "выступил"]
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert sentence == ["сказал", ":", "старый", "Ветеран", "выступил"]

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

    # 2026-07 annotation pass: 10/100 pleonasm outputs were non-words.
    # Root causes fixed below; per-record regressions.

    def test_vpervye_entry_inert_multiword(self):
        # Audit C3 (2026-07): the "впервые" -> "в первый раз" entry inserts a
        # 3-word phrase into a single corrupted-token slot with one $DELETE
        # tag. Re-splitting the corrupted sentence on whitespace downstream
        # then desyncs token/tag counts (one tag, three surface tokens) —
        # the ErrorResult contract can't express a per-token multiword
        # insertion, so multiword entries are now permanently filtered out
        # (see PleonasmHandler._entry_blocked and pleonasms.json's _meta).
        # "впервые" has no other entry, so it no longer fires at all.
        tokens = [
            _tok("посещает", pos="VERB", lemma="посещать", idx=0),
            _tok("впервые", pos="ADV", lemma="впервые", idx=1),
            _tok("за", pos="ADP", lemma="за", idx=2),
            _tok("десятилетие", lemma="десятилетие", idx=3),
        ]
        assert self.handler.can_apply(tokens, 1) is False
        sentence = ["посещает", "впервые", "за", "десятилетие"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is None
        assert sentence == ["посещает", "впервые", "за", "десятилетие"]

    def test_tolpa_blocked_when_complement_follows(self):
        # "учиненный толпой демонстрантов" → inserting the genitive attribute
        # severed the core from its own complement ("толпой народу
        # демонстрантов").
        tokens = [
            _tok("толпой", lemma="толпа", idx=0),
            _tok("демонстрантов", lemma="демонстрант", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = ["толпой", "демонстрантов"]
        assert self.handler.apply(tokens, sentence, 0, set()) is None
        assert sentence == ["толпой", "демонстрантов"]

    def test_tolpa_naroda_fires_standalone(self):
        # Without a following complement the entry still fires, with the
        # standard genitive form ("народа", not the partitive "народу").
        tokens = [
            _tok("собралась", pos="VERB", lemma="собраться", idx=0),
            _tok("толпа", lemma="толпа", idx=1),
        ]
        sentence = ["собралась", "толпа"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert sentence == ["собралась", "толпа", "народа"]

    def test_propn_core_skipped(self):
        # The spacecraft "Прогресс М1-11" got "вперёд" injected into its
        # name; PROPN cores are names, not the dictionary word.
        tokens = [_tok("Династия", pos="PROPN", lemma="династия", idx=0)]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = ["Династия"]
        assert self.handler.apply(tokens, sentence, 0, set()) is None

    def test_progress_entry_rekeyed_to_verb(self):
        # "прогресс вперёд" is never grammatical for the noun; the attested
        # pleonasm is the verb ("прогрессировать вперёд"). Entry re-keyed.
        tokens = [_tok("прогресс", lemma="прогресс", idx=0)]
        assert self.handler.can_apply(tokens, 0) is False
        tokens = [
            _tok("болезнь", lemma="болезнь", idx=0),
            _tok("прогрессирует", pos="VERB", lemma="прогрессировать", idx=1),
        ]
        sentence = ["болезнь", "прогрессирует"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert sentence == ["болезнь", "прогрессирует", "вперёд"]

    def test_konechny_itog_idiom_blocked(self):
        # "в конечном итоге" is a frozen adverbial idiom — "в окончательном
        # конечном итоге" was garbage. "конечная остановка" (see
        # test_adjective_core_agreement) must keep firing.
        tokens = [
            _tok("в", pos="ADP", lemma="в", idx=0),
            _tok("конечном", pos="ADJ", lemma="конечный", idx=1),
            _tok("итоге", lemma="итог", idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is False
        sentence = ["в", "конечном", "итоге"]
        assert self.handler.apply(tokens, sentence, 1, set()) is None

    @pytest.mark.parametrize("numeral", ["три", "13"])
    def test_polovina_blocked_in_numeric_construction(self, numeral):
        # "три с половиной процента" → "три с большей половиной" was garbage:
        # "<numeral> с половиной" is a quantity construction, not the
        # «большая половина» pleonasm target.
        tokens = [
            _tok("на", pos="ADP", lemma="на", idx=0),
            _tok(numeral, pos="NUM", lemma=numeral, idx=1),
            _tok("с", pos="ADP", lemma="с", idx=2),
            _tok("половиной", lemma="половина", idx=3),
            _tok("процента", lemma="процент", idx=4),
        ]
        assert self.handler.can_apply(tokens, 3) is False
        sentence = [t.text for t in tokens]
        assert self.handler.apply(tokens, sentence, 3, set()) is None

    def test_polovina_fires_outside_numeric_construction(self):
        # "большая половина зрителей" is the textbook pleonasm and must
        # survive the numeric guard (before-inserts are exempt from the
        # complement guard).
        tokens = [
            _tok("половина", lemma="половина", idx=0),
            _tok("зрителей", lemma="зритель", idx=1),
        ]
        sentence = ["половина", "зрителей"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence == ["большая", "половина", "зрителей"]

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

    def test_no_multiword_entry_ever_selected(self):
        # Audit C3 invariant, checked against the full loaded lexicon: no
        # entry whose "word" contains a space may ever be picked, for any
        # core lemma, regardless of position/context. A single $DELETE tag
        # cannot express a multiword insertion without desyncing the
        # token/tag counts once the corrupted sentence is re-split on
        # whitespace.
        for lemma, entries in self.handler.pleonasms.items():
            for entry in entries:
                if " " not in entry["word"]:
                    continue
                assert self.handler._entry_blocked(
                    [_tok(lemma, lemma=lemma, idx=0)], 0, entry
                ), (lemma, entry)


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

    # 2026-07 annotation pass: 20/73 collocation outputs did not carry the
    # original token's form (short participles came out as finite verbs,
    # passive participles as active: "принято"→"сделало", "нанесен"→"оказал").
    # The replacement now receives the original's form-level grammemes (POS
    # class, voice, tense, gender, number, case) via the paronym handler's
    # grammeme-transfer approach, and the handler skips when the transfer
    # cannot be realized.

    def test_short_participle_neut_preserved(self):
        # "принято решение" → "сделано", NOT the finite past "сделало"
        tokens = [
            _tok("принято", pos="VERB", lemma="принять", idx=0),
            _tok("решение", lemma="решение", idx=1),
        ]
        sentence = ["принято", "решение"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] == "сделано"

    def test_short_participle_masc_voice_preserved(self):
        # "нанесен ущерб" → "оказан", NOT the finite active "оказал"
        tokens = [
            _tok("нанесен", pos="VERB", lemma="нанести", idx=0),
            _tok("ущерб", lemma="ущерб", idx=1),
        ]
        sentence = ["нанесен", "ущерб"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] == "оказан"

    def test_full_participle_voice_preserved(self):
        # "нанесенный ущерб" → "оказанный" (passive), NOT "оказавший" (active)
        tokens = [
            _tok("нанесенный", pos="VERB", lemma="нанести", idx=0),
            _tok("ущерб", lemma="ущерб", idx=1),
        ]
        sentence = ["нанесенный", "ущерб"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] == "оказанный"

    def test_full_participle_oblique_case_preserved(self):
        # "принятом решении" → "сделанном" (locative kept), NOT "сделавшем"
        tokens = [
            _tok("принятом", pos="VERB", lemma="принять", idx=0),
            _tok("решении", lemma="решение", idx=1),
        ]
        sentence = ["принятом", "решении"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] == "сделанном"

    def test_adjectivized_participle_recovers_via_verb_parse(self):
        # parse("установленный")[0] is the lexicalized *adjective*, whose
        # ADJF grammemes no verb lexeme can realize; the handler must fall
        # through to the PRTF parse and yield the passive participle
        # ("завоёванный"), not the active "завоевавший" and not a skip.
        tokens = [
            _tok("установленный", pos="VERB", lemma="установить", idx=0),
            _tok("рекорд", lemma="рекорд", idx=1),
        ]
        sentence = ["установленный", "рекорд"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] == "завоёванный"

    def test_skips_when_inflection_fails(self):
        # Precision-first: when no parse of the replacement can realize the
        # original's grammemes, the handler must skip — not fall back to the
        # citation form (which stacked a form error on top of the Lex error).
        handler = CollocationHandler()
        handler._collocations = {"принять": [{"wrong": "стол", "collocate": "решение"}]}
        tokens = [
            _tok("принято", pos="VERB", lemma="принять", idx=0),
            _tok("решение", lemma="решение", idx=1),
        ]
        sentence = ["принято", "решение"]
        assert handler.apply(tokens, sentence, 0, set()) is None
        assert sentence == ["принято", "решение"]

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
