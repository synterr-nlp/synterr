"""Tests for AdverbSpellingHandler — solid/separate/hyphen confusion."""

from functools import partial
from random import Random

import pytest

from synterr.languages.russian.errors.adverb_spelling import AdverbSpellingHandler

from .helpers import make_token

_tok = partial(make_token, pos="ADV")


class TestProtocol:
    handler = AdverbSpellingHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "adverb_spelling"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 4

    def test_set_subtype_weights(self):
        h = AdverbSpellingHandler()
        h.set_subtype_weights({"adverb_solid_to_separate": 100})
        assert h._weights["adverb_solid_to_separate"] == 100
        assert h._weights["adverb_separate_to_solid"] == 30  # default preserved


class TestSolidToSeparate:
    def test_split_solid_adverb(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("наверх")]
        sentence = ["наверх"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_solid_to_separate"
        assert sentence == ["на", "верх"]


class TestNoSuffixDerivedSplits:
    """Regression: suffix-derived adverbs (довольный → довольно etc.) must
    never be split — they are not §53–58 prep+noun formations, and the cut
    lands inside the root ("до вольно", "на прасно")."""

    NON_SPLITTABLE = ["довольно", "напрасно", "поочерёдно", "попарно", "вполне"]

    @pytest.mark.parametrize("word", NON_SPLITTABLE)
    def test_can_apply_false(self, word):
        h = AdverbSpellingHandler()
        assert h.can_apply([_tok(word)], 0) is False

    @pytest.mark.parametrize("word", NON_SPLITTABLE)
    def test_apply_returns_none(self, word):
        h = AdverbSpellingHandler()
        sentence = [word]
        result = h.apply([_tok(word)], sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence == [word]

    def test_reverse_pairs_also_removed(self):
        """Auto-derived merge pairs ("до" + "вольно" → "довольно") must be
        gone too — they would 'correct' text that was never a learner split."""
        h = AdverbSpellingHandler()
        tokens = [_tok("до", pos="ADP"), _tok("вольно", idx=1)]
        assert h.can_apply(tokens, 0) is False
        assert h.apply(tokens, ["до", "вольно"], 0, set(), rng=Random(0)) is None


class TestHyphenToSeparate:
    def test_remove_hyphen(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("по-русски")]
        sentence = ["по-русски"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_hyphen_to_separate"
        assert sentence == ["по", "русски"]


class TestSeparateToSolid:
    def test_merge_prep_noun(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("на", pos="ADP"), _tok("верх", pos="NOUN", idx=1)]
        sentence = ["на", "верх"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_separate_to_solid"
        assert sentence == ["наверх"]


class TestNoMergeForAdverbialPrepositions:
    """Regression (§56 п.7 прим.1–2): spatial/temporal words like посередине,
    наверху, внизу keep SOLID spelling even with a governed noun, so merging
    'по середине комнаты' → 'посередине комнаты' produces CORRECT Russian —
    a non-error. The merge direction must be disabled for this family."""

    SPATIAL_PAIRS = [
        ("по", "середине"),
        ("на", "верху"),
        ("в", "низу"),
        ("в", "верху"),
        ("с", "боку"),
        ("с", "верху"),
        ("с", "низу"),
        ("в", "глубь"),
        ("в", "даль"),
        ("в", "дали"),
        ("по", "верх"),
        ("по", "зади"),
        ("в", "переди"),
    ]

    @pytest.mark.parametrize(("prep", "noun"), SPATIAL_PAIRS)
    def test_merge_disabled(self, prep, noun):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_separate_to_solid"})
        tokens = [_tok(prep, pos="ADP"), _tok(noun, pos="NOUN", idx=1)]
        sentence = [prep, noun]
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None
        assert sentence == [prep, noun]

    @pytest.mark.parametrize(
        "solid",
        ["посередине", "наверху", "внизу", "сбоку", "вглубь", "впереди"],
    )
    def test_forward_split_still_works(self, solid):
        """Splitting the bare solid adverb remains a real error."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        sentence = [solid]
        result = h.apply([_tok(solid)], sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_solid_to_separate"


class TestOtovsyuduNotSplit:
    """Regression: отовсюду is a §56 п.1 prefix+adverb formation (ото-+всюду);
    the old entry split inside the prefix ('от овсюду' — non-word)."""

    def test_can_apply_false(self):
        h = AdverbSpellingHandler()
        assert h.can_apply([_tok("отовсюду")], 0) is False

    def test_apply_returns_none(self):
        h = AdverbSpellingHandler()
        sentence = ["отовсюду"]
        assert h.apply([_tok("отовсюду")], sentence, 0, set(), rng=Random(0)) is None
        assert sentence == ["отовсюду"]


class TestVekiHomographGuard:
    """Regression: 'на веки' with lemma веко (eyelids) must NOT merge —
    'Нанесите крем навеки' is fluent Russian, not a spelling error."""

    def test_eyelids_not_merged(self):
        h = AdverbSpellingHandler()
        # stanza lemmatizes веки → веко in 'крем на веки'
        tokens = [_tok("на", pos="ADP"), _tok("веки", pos="NOUN", lemma="веко", idx=1)]
        sentence = ["на", "веки"]
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None
        assert sentence == ["на", "веки"]

    def test_time_noun_still_merges(self):
        """век 'age' reading (на веки вечные) is the §56 п.7 прим.1 word."""
        h = AdverbSpellingHandler()
        tokens = [_tok("на", pos="ADP"), _tok("веки", pos="NOUN", lemma="век", idx=1)]
        sentence = ["на", "веки"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["навеки"]


class TestPodryadNounGuard:
    """Regression: подряд as the noun 'contract' (выиграть подряд на ремонт)
    must not be split into the non-word 'по дряд' (§56 п.6 lists подряд as
    adverb only)."""

    def test_noun_pos_blocked(self):
        h = AdverbSpellingHandler()
        assert h.can_apply([_tok("подряд", pos="NOUN")], 0) is False

    def test_contract_context_blocked_despite_adv_tag(self):
        """stanza tags the contract reading ADV too — context guard needed."""
        h = AdverbSpellingHandler()
        tokens = [
            _tok("выиграла", pos="VERB", lemma="выиграть"),
            _tok("подряд", pos="ADV", idx=1),
            _tok("на", pos="ADP", idx=2),
            _tok("ремонт", pos="NOUN", idx=3),
        ]
        assert h.can_apply(tokens, 1) is False
        sentence = ["выиграла", "подряд", "на", "ремонт"]
        assert h.apply(tokens, sentence, 1, set(), rng=Random(0)) is None
        assert sentence == ["выиграла", "подряд", "на", "ремонт"]

    def test_adverbial_reading_still_splits(self):
        h = AdverbSpellingHandler()
        tokens = [
            _tok("шли", pos="VERB", lemma="идти"),
            _tok("подряд", pos="ADV", idx=1),
            _tok("часами", pos="NOUN", idx=2),
        ]
        assert h.can_apply(tokens, 1) is True
        sentence = ["шли", "подряд", "часами"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["шли", "по", "дряд", "часами"]


class TestSplitAmbiguityGuards:
    """Regression (audit B12): solid→separate lacked the ambiguity guards the
    merge direction has. A governed genitive sanctions the separate spelling
    (§53 прим.: 'движение в глубь Чечни' is normative), and homographs like
    навстречу/вначале have a fluent PP reading even bare ('идёт на встречу',
    'В начале было слово') — splitting there is not an error."""

    GEN_BLOCKED_CASES = [
        # (adverb, following genitive nominal)
        ("вглубь", "Чечни"),
        ("вдаль", "моря"),
        ("вверх", "страницы"),
        ("вовремя", "грозы"),
        ("наконец", "года"),
        ("сначала", "века"),
    ]

    @pytest.mark.parametrize(("adverb", "gen_noun"), GEN_BLOCKED_CASES)
    def test_gen_complement_blocks_split(self, adverb, gen_noun):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        tokens = [
            _tok(adverb),
            _tok(gen_noun, pos="NOUN", idx=1, features={"Case": "Gen"}),
        ]
        sentence = [adverb, gen_noun]
        assert h.can_apply(tokens, 0) is False
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None
        assert sentence == [adverb, gen_noun]

    def test_gen_agreeing_adjective_blocks_split(self):
        """'в глубь синего моря' — the agreeing ADJ carries the genitive."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        tokens = [
            _tok("вглубь"),
            _tok("синего", pos="ADJ", idx=1, features={"Case": "Gen"}),
            _tok("моря", pos="NOUN", idx=2, features={"Case": "Gen"}),
        ]
        sentence = ["вглубь", "синего", "моря"]
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None

    def test_bare_vverh_still_fires(self):
        """'Он посмотрел вверх' — no governed noun, split is a clear error."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        tokens = [
            _tok("посмотрел", pos="VERB", lemma="посмотреть"),
            _tok("вверх", idx=1),
            _tok(".", pos="PUNCT", idx=2),
        ]
        sentence = ["посмотрел", "вверх", "."]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_solid_to_separate"
        assert sentence == ["посмотрел", "в", "верх", "."]

    def test_non_gen_complement_still_fires(self):
        """A following non-genitive nominal does not sanction the separate
        spelling — 'ушёл вовремя' with Nom subject after stays corruptible."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        tokens = [
            _tok("наконец"),
            _tok("он", pos="PRON", idx=1, features={"Case": "Nom"}),
        ]
        sentence = ["наконец", "он"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["на", "конец", "он"]

    def test_navstrechu_bare_blocked(self):
        """'Он идёт навстречу' → 'идёт на встречу' (to a meeting) is fully
        normative — a fluent meaning change, not a spelling error."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        tokens = [
            _tok("идёт", pos="VERB", lemma="идти"),
            _tok("навстречу", idx=1),
            _tok(".", pos="PUNCT", idx=2),
        ]
        sentence = ["идёт", "навстречу", "."]
        assert h.can_apply(tokens, 1) is False
        assert h.apply(tokens, sentence, 1, set(), rng=Random(0)) is None

    def test_navstrechu_with_dative_fires(self):
        """'навстречу ветру' → 'на встречу ветру' IS an error (§53 п.5):
        the PP 'на встречу' does not govern a bare dative."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        tokens = [
            _tok("навстречу"),
            _tok("ветру", pos="NOUN", idx=1, features={"Case": "Dat"}),
        ]
        sentence = ["навстречу", "ветру"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["на", "встречу", "ветру"]

    def test_vnachale_always_blocked(self):
        """'Вначале было слово' → 'В начале было слово' is the canonical
        biblical spelling; no context reliably rules the PP reading out."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        tokens = [
            _tok("Вначале"),
            _tok("было", pos="VERB", idx=1),
            _tok("слово", pos="NOUN", idx=2, features={"Case": "Nom"}),
        ]
        sentence = ["Вначале", "было", "слово"]
        assert h.can_apply(tokens, 0) is False
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None
        assert sentence == ["Вначале", "было", "слово"]


class TestToParticleGuard:
    """Regression (§57 п.3): the -то hyphen belongs to the indefinite
    particle; pronominal/demonstrative то must not be merged."""

    def test_to_i_delo_idiom_blocked(self):
        h = AdverbSpellingHandler()
        tokens = [
            _tok("когда", pos="SCONJ"),
            _tok("то", pos="DET", lemma="тот", idx=1),
            _tok("и", pos="PART", idx=2),
            _tok("дело", pos="NOUN", idx=3),
        ]
        sentence = ["когда", "то", "и", "дело"]
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None
        assert sentence == ["когда", "то", "и", "дело"]

    def test_pronoun_to_blocked(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("где", pos="ADV"), _tok("то", pos="PRON", lemma="тот", idx=1)]
        sentence = ["где", "то"]
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None

    def test_correlative_clause_blocked(self):
        """'Сделай так, как то советовал отец' — merged form reads as valid
        Russian with changed meaning."""
        h = AdverbSpellingHandler()
        tokens = [
            _tok(",", pos="PUNCT"),
            _tok("как", pos="SCONJ", idx=1),
            _tok("то", pos="PART", idx=2),
            _tok("советовал", pos="VERB", idx=3),
            _tok("отец", pos="NOUN", idx=4),
        ]
        sentence = [",", "как", "то", "советовал", "отец"]
        assert h.apply(tokens, sentence, 1, set(), rng=Random(0)) is None

    def test_genuine_particle_error_still_fires(self):
        """'Он куда то ушёл' — standard learner spelling, must still merge."""
        h = AdverbSpellingHandler()
        tokens = [
            _tok("Он", pos="PRON"),
            _tok("куда", pos="ADV", idx=1),
            _tok("то", pos="PART", idx=2),
            _tok("ушёл", pos="VERB", idx=3),
        ]
        sentence = ["Он", "куда", "то", "ушёл"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_separate_to_hyphen"
        assert sentence == ["Он", "куда-то", "ушёл"]

    def test_nibud_pairs_unaffected(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("где", pos="ADV"), _tok("нибудь", pos="PART", idx=1)]
        sentence = ["где", "нибудь"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["где-нибудь"]


class TestMultiHyphenAdverbs:
    """Regression: точь-в-точь must split on ALL hyphens (the learner error
    is 'точь в точь', not the half-form 'точь-в точь'); бок-о-бок is itself
    a misspelling (§58 п.1: 'бок о бок') and is generated as the ERROR."""

    def test_toch_v_toch_full_split(self):
        h = AdverbSpellingHandler()
        sentence = ["точь-в-точь"]
        result = h.apply([_tok("точь-в-точь")], sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_hyphen_to_separate"
        assert sentence == ["точь", "в", "точь"]
        assert result.end_idx == 2

    def test_bok_o_bok_headword_removed(self):
        """'бок-о-бок' is not a correct form — never treated as splittable."""
        h = AdverbSpellingHandler()
        assert h.can_apply([_tok("бок-о-бок")], 0) is False

    def test_bok_o_bok_generated_as_error(self):
        h = AdverbSpellingHandler()
        tokens = [
            _tok("бок", pos="NOUN"),
            _tok("о", pos="ADP", idx=1),
            _tok("бок", pos="NOUN", idx=2),
        ]
        sentence = ["бок", "о", "бок"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_separate_to_hyphen"
        assert sentence == ["бок-о-бок"]
        assert result.original == "бок о бок"
        assert result.fix_tag == "$SPLIT_бок_о_бок"

    def test_toch_v_toch_not_re_merged(self):
        """No reverse merge for точь в точь: the separate form is the error,
        merging it would CORRECT the text, not corrupt it."""
        h = AdverbSpellingHandler()
        tokens = [
            _tok("точь", pos="ADV"),
            _tok("в", pos="ADP", idx=1),
            _tok("точь", pos="ADV", idx=2),
        ]
        sentence = ["точь", "в", "точь"]
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None


class TestMergeBookkeeping:
    """Regression: merges must not swallow a neighbor token already corrupted
    by another handler, and must look up the LIVE sentence text."""

    def test_modified_neighbor_blocks_merge(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("на", pos="ADP"), _tok("верх", pos="NOUN", idx=1)]
        sentence = ["на", "верх"]
        result = h.apply(tokens, sentence, 0, {1}, rng=Random(0))
        assert result is None
        assert sentence == ["на", "верх"]

    def test_live_sentence_text_used_for_pair(self):
        """If the live sentence no longer matches the analyzed pair, the
        merge must not fire off stale token text."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_separate_to_solid"})
        tokens = [_tok("на", pos="ADP"), _tok("верх", pos="NOUN", idx=1)]
        sentence = ["на", "верхе"]  # corrupted by another handler, not marked
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence == ["на", "верхе"]

    def test_dep_guard_blocks_live_np(self):
        """With depparse: a noun heading its own NP ('в начале осени') is a
        live syntactic phrase — skip the merge."""
        h = AdverbSpellingHandler()
        tokens = [
            _tok("в", pos="ADP", head_idx=1),
            _tok("начале", pos="NOUN", idx=1, head_idx=None),
            _tok("осени", pos="NOUN", idx=2, head_idx=1),  # depends on начале
        ]
        sentence = ["в", "начале", "осени"]
        assert h.apply(tokens, sentence, 0, set(), rng=Random(0)) is None


class TestFixTagFormat:
    """Regression: $SPLIT_ tags use underscore separators (matching
    function_spelling) — a space inside a tag breaks whitespace-tokenized
    tag parsing."""

    def test_split_tag_uses_underscore(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("на", pos="ADP"), _tok("верх", pos="NOUN", idx=1)]
        sentence = ["на", "верх"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.fix_tag == "$SPLIT_на_верх"
        assert " " not in result.fix_tag


class TestEnabledSubtypes:
    """set_enabled_subtypes restricts which subtype apply() may emit."""

    def test_filter_emits_only_requested_subtype(self):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        for seed in range(10):
            sentence = ["наверх"]
            result = h.apply([_tok("наверх")], sentence, 0, set(), rng=Random(seed))
            assert result is not None
            assert result.error_type == "adverb_spelling_adverb_solid_to_separate"
            assert sentence == ["на", "верх"]

    def test_filter_returns_none_when_subtype_unavailable(self):
        """A solid adverb cannot be merged (separate_to_solid); requesting that
        subtype must decline rather than fall back to solid_to_separate."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_separate_to_solid"})
        sentence = ["наверх"]
        result = h.apply([_tok("наверх")], sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence == ["наверх"]

    def test_filter_allows_merge_on_two_token_sequence(self):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_separate_to_solid"})
        tokens = [_tok("на", pos="ADP"), _tok("верх", pos="NOUN", idx=1)]
        sentence = ["на", "верх"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_separate_to_solid"
        assert sentence == ["наверх"]

    def test_none_means_all(self):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        h.set_enabled_subtypes(None)
        assert h._enabled_subtypes is None

    def test_invalid_subtype_raises(self):
        h = AdverbSpellingHandler()
        with pytest.raises(ValueError, match="Unknown subtypes"):
            h.set_enabled_subtypes({"not_a_subtype"})
