"""Tests for OrthographicSpellingHandler — morpheme-level spelling rules."""

from random import Random

import pytest

from synterr.languages.russian.errors.orthographic_spelling import (
    OrthographicSpellingHandler,
)

from .helpers import make_token as _tok


def _force_subtype(subtype: str) -> OrthographicSpellingHandler:
    """Create handler with only one subtype active (weight=100, rest=0)."""
    h = OrthographicSpellingHandler()
    weights = {s: 0 for s in h.subtypes}
    weights[subtype] = 100
    h.set_subtype_weights(weights)
    return h


class TestProtocol:
    handler = OrthographicSpellingHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "orthographic_spelling"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is False
        assert len(self.handler.subtypes) == 12

    def test_set_subtype_weights(self):
        h = OrthographicSpellingHandler()
        h.set_subtype_weights({"pre_pri": 100})
        assert h._weights["pre_pri"] == 100
        assert h._weights["suffix_ek_ik"] == 8  # default


class TestPrePri:
    """пре-/при- prefix confusion."""

    def test_pre_to_pri(self):
        h = _force_subtype("pre_pri")
        # Use word with confirmed пре- prefix per morpheme dict
        tokens = [_tok("превысить", pos="VERB")]
        sentence = ["превысить"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "привысить"

    def test_pri_to_pre(self):
        h = _force_subtype("pre_pri")
        tokens = [_tok("приступить", pos="VERB")]
        sentence = ["приступить"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "преступить"

    def test_preserves_case(self):
        h = _force_subtype("pre_pri")
        tokens = [_tok("Приступить", pos="VERB")]
        sentence = ["Приступить"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "Преступить"

    def test_inflected_form_fires_via_lemma_fallback(self):
        # Morpheme dict is lemma-keyed; the surface "пребывает" is OOV
        # but the lemma confirms the пре- prefix (LoRuGEC canonical case)
        h = _force_subtype("pre_pri")
        tokens = [_tok("пребывает", pos="VERB", lemma="пребывать")]
        sentence = ["пребывает"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "прибывает"

    def test_oov_surface_and_lemma_still_skipped(self):
        h = _force_subtype("pre_pri")
        tokens = [_tok("председатель", pos="NOUN", lemma="председатель")]
        sentence = ["председатель"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None or sentence[0] == "председатель"

    def test_short_word_rejected(self):
        h = OrthographicSpellingHandler()
        tokens = [_tok("при", pos="ADP")]
        assert not h.can_apply(tokens, 0)  # too short


class TestYiAfterPrefix:
    """ы/и after consonant-ending prefix.

    Audit fix O3: has_prefix must resolve True (surface, or lemma fallback)
    before swapping — previously an unverified ("None") result was only
    rejected for prefixes of 2 chars or less, so longer "prefixes" (полит-,
    сверх-...) passed through unverified. Words below are chosen so the
    prefix is actually confirmed via the unified morpheme dict (surface
    directly, or via an explicit lemma — mirroring how pre_pri's lemma
    fallback is tested).
    """

    def test_i_to_y_russian_prefix(self):
        """без- (Russian prefix) is dict-confirmed directly on the surface."""
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("безызвестный", pos="ADJ")]
        sentence = ["безызвестный"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "безизвестный"

    def test_i_to_y_russian_prefix_lemma_fallback(self):
        """Misspelled surface (и) is OOV; the correctly-spelled lemma (ы)
        confirms без- as a real prefix, mirroring pre_pri's lemma fallback."""
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("безизвестный", pos="ADJ", lemma="безызвестный")]
        sentence = ["безизвестный"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "безызвестный"

    def test_y_to_i_foreign_prefix(self):
        """дез- (foreign prefix) is dict-confirmed directly on the surface."""
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("дезинфекция", pos="NOUN")]
        sentence = ["дезинфекция"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "дезынфекция"

    def test_y_to_i_foreign_prefix_kontr(self):
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("контригра", pos="NOUN")]
        sentence = ["контригра"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "контрыгра"

    def test_podytog_lemma_fallback(self):
        """The inflected surface is OOV; the infinitive lemma подытожить
        confirms под- as a real prefix (LoRuGEC-style inflected form)."""
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("подитожила", pos="VERB", lemma="подытожить")]
        sentence = ["подитожила"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "подытожила"

    def test_sverkh_unverifiable_now_skipped(self):
        """сверх- has no и-initial-root entries at all in the morpheme
        dict (neither surface nor lemma), so it can no longer be verified
        — this now skips instead of guessing (was previously "fixed" only
        because sверх (5 chars) fell through the old len(pfx)<=2 escape
        hatch unverified)."""
        h = _force_subtype("y_i_after_prefix")
        tokens = [
            _tok(
                "сверхындустриализации",
                pos="NOUN",
                lemma="сверхындустриализация",
            )
        ]
        sentence = ["сверхындустриализации"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "сверхындустриализации"

    def test_politicheskomu_not_mangled(self):
        """Audit bug: "полит" in политическому/-ий is the ROOT of
        политический (per Tikhonov), not a real prefix — has_prefix on the
        lemma correctly resolves False, so this must be skipped rather
        than corrupted into "политыческому"."""
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("политическому", pos="ADJ", lemma="политический")]
        sentence = ["политическому"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "политическому"


class TestSuffixEnkOnk:
    """-еньк/-оньк swap."""

    def test_onk_to_enk(self):
        h = _force_subtype("suffix_enk_onk")
        tokens = [_tok("душонька")]
        sentence = ["душонька"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "душенька"

    def test_enk_to_onk(self):
        h = _force_subtype("suffix_enk_onk")
        tokens = [_tok("рыбенька")]
        sentence = ["рыбенька"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "рыбонька"


class TestSuffixInskEnsk:
    """-инск/-енск swap."""

    def test_ensk_to_insk(self):
        h = _force_subtype("suffix_insk_ensk")
        tokens = [_tok("керченский", pos="ADJ")]
        sentence = ["керченский"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "керчинский"

    def test_insk_to_ensk(self):
        h = _force_subtype("suffix_insk_ensk")
        tokens = [_tok("ялтинский", pos="ADJ")]
        sentence = ["ялтинский"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "ялтенский"

    def test_propn_not_swapped(self):
        """Proper nouns like Минск should NOT be corrupted."""
        h = _force_subtype("suffix_insk_ensk")
        tokens = [_tok("Минск", pos="PROPN")]
        sentence = ["Минск"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "Минск"


class TestSuffixItsEts:
    """-иц/-ец swap in neuter nouns."""

    def test_ets_to_its(self):
        h = _force_subtype("suffix_its_ets")
        tokens = [_tok("пальтецо")]
        sentence = ["пальтецо"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "пальтицо"

    def test_its_to_ets(self):
        h = _force_subtype("suffix_its_ets")
        tokens = [_tok("креслице")]
        sentence = ["креслице"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "креслеце"

    def test_root_ица_not_swapped(self):
        """лицами has иц in root, not suffix — should NOT be swapped."""
        h = _force_subtype("suffix_its_ets")
        tokens = [_tok("лицами")]
        sentence = ["лицами"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "лицами"


class TestSuffixEkIk:
    """-ек/-ик swap."""

    def test_ik_to_ek(self):
        h = _force_subtype("suffix_ek_ik")
        # Use word with confirmed -ик suffix per morpheme dict
        tokens = [_tok("столик")]
        sentence = ["столик"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "столек"

    def test_ek_to_ik(self):
        h = _force_subtype("suffix_ek_ik")
        # Use word with confirmed -ек suffix per morpheme dict
        tokens = [_tok("замочек")]
        sentence = ["замочек"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "замочик"

    def test_unknown_word_rejected(self):
        h = _force_subtype("suffix_ek_ik")
        # Words without confirmed suffix are rejected
        tokens = [_tok("человек")]
        sentence = ["человек"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        # Should return None — человек has no -ек suffix per morpheme dict
        assert result is None or sentence[0] == "человек"


class TestParticipleSuffix:
    """Conjugation-dependent participle suffix swaps.

    Audit fix O1: the suffix span is now located via the anchored terminal
    regex (not a blind ``str.find``, which could hit a root-internal
    lookalike) and confirmed via the morpheme dict — surface first, then
    the lemma, mirroring pre_pri's lemma fallback. Tikhonov's dictionary
    covers word *formation*, not participle inflection, so live participle
    surfaces (борющийся, дышащий...) are themselves always OOV; the
    infinitive lemma is what actually resolves the check (it shares the
    same PREF+ROOT region as the participle). Tokens below carry that
    realistic lemma explicitly, exactly as the real stanza-backed pipeline
    would for a VERB-tagged participle.
    """

    def test_ushch_to_ashch(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("борющийся", pos="ADJ", lemma="бороться")]
        sentence = ["борющийся"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "борящийся"

    def test_ashch_to_ushch(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("дышащий", pos="ADJ", lemma="дышать")]
        sentence = ["дышащий"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "дышущий"

    def test_em_to_im(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("изучаемого", pos="ADJ", lemma="изучать")]
        sentence = ["изучаемого"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "изучаимого"

    def test_im_to_em(self):
        """зависимый is directly in the morpheme dict as its own lemma —
        no lemma fallback needed."""
        h = _force_subtype("participle_suffix")
        tokens = [_tok("зависимый", pos="ADJ")]
        sentence = ["зависимый"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "зависемый"

    def test_yushch_to_yashch(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("колющей", pos="ADJ", lemma="колоть")]
        sentence = ["колющей"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "колящей"

    def test_unverifiable_participle_skipped(self):
        """No dict data at all (surface OOV, lemma also OOV/absent) —
        must skip rather than fall back to the old "unknown word — allow"
        bypass."""
        h = _force_subtype("participle_suffix")
        tokens = [_tok("бренчащий", pos="ADJ", lemma="бренчащий")]
        sentence = ["бренчащий"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "бренчащий"

    def test_ushchemlyayushchiy_not_mangled(self):
        """Audit bug B2: a blind textual find() for "ущ" hit the
        root-initial "ущ" of "Ущемляющий" (root у-щемл-) instead of the
        real "ющ" suffix right before the "ий" ending. The anchored
        terminal regex must locate the real suffix and swap only that."""
        h = _force_subtype("participle_suffix")
        tokens = [_tok("Ущемляющий", pos="VERB", lemma="ущемлять")]
        sentence = ["Ущемляющий"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "Ущемляящий"

    def test_priemlemyy_not_mangled(self):
        """Audit bug B2: find() hit the root-final "ем" inside "приемл"
        instead of the real suffix "ем" right before "ый"."""
        h = _force_subtype("participle_suffix")
        tokens = [_tok("приемлемый", pos="ADJ")]
        sentence = ["приемлемый"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "приемлимый"

    def test_nepримirimykh_not_mangled(self):
        """Audit bug B2 (lenta): find() hit "им" spanning the при-/мир-
        prefix/root boundary instead of the real suffix "им" before "ых"."""
        h = _force_subtype("participle_suffix")
        tokens = [_tok("непримиримых", pos="ADJ", lemma="непримиримый")]
        sentence = ["непримиримых"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "непримиремых"


class TestNNSuffix:
    """н/нн in adjective suffixes.

    Audit fix O2: the н/нн position is now confirmed via the morpheme dict
    (surface first, lemma fallback) to sit at a root/suffix boundary
    before editing — not just "some нн/ан/ян/ин exists somewhere in the
    word" (which picked up root-internal doubles/sequences).
    """

    def test_nn_to_n_gosudarstvenny(self):
        h = _force_subtype("nn_suffix")
        tokens = [_tok("государственный", pos="ADJ")]
        sentence = ["государственный"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "государственый"

    def test_nn_to_n_gosudarstvennogo_oblique(self):
        """Genitive form — surface OOV, verified via the lemma fallback."""
        h = _force_subtype("nn_suffix")
        tokens = [_tok("государственного", pos="ADJ", lemma="государственный")]
        sentence = ["государственного"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "государственого"

    def test_n_to_nn_kozhanyy(self):
        h = _force_subtype("nn_suffix")
        tokens = [_tok("кожаный", pos="ADJ")]
        sentence = ["кожаный"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "кожанный"

    def test_yaltinskiy_still_fires(self):
        """-инск- (SUFF at a confirmed root boundary) is a valid doubling
        target — preserves the existing TestEnabledSubtypes coverage."""
        h = _force_subtype("nn_suffix")
        tokens = [_tok("ялтинский", pos="ADJ")]
        sentence = ["ялтинский"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None

    def test_tonnelnyy_not_mangled(self):
        """Audit bug B3: "нн" in тоннельный is entirely root-internal (the
        loanword root "тоннель") — the real suffix is a single "н". No
        genuine нн/ан/ян/ин target exists, so this must be skipped."""
        h = _force_subtype("nn_suffix")
        tokens = [_tok("тоннельный", pos="ADJ")]
        sentence = ["тоннельный"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "тоннельный"

    def test_alyuminievyy_not_mangled(self):
        """Audit bug B3: "ин" in алюминиевый is root-internal (root
        "алюмин"), not the -ин- adjectival suffix — must be skipped."""
        h = _force_subtype("nn_suffix")
        tokens = [_tok("алюминиевый", pos="ADJ")]
        sentence = ["алюминиевый"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "алюминиевый"


class TestVowelAfterTs:
    """Vowel swaps after ц."""

    def test_o_to_e(self):
        h = _force_subtype("vowel_after_ts")
        tokens = [_tok("герцога")]
        sentence = ["герцога"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "герцега"

    def test_i_to_y(self):
        h = _force_subtype("vowel_after_ts")
        tokens = [_tok("циганский", pos="ADJ")]
        sentence = ["циганский"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "цыганский"

    def test_y_to_i(self):
        h = _force_subtype("vowel_after_ts")
        tokens = [_tok("цыновками")]
        sentence = ["цыновками"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "циновками"


class TestVowelAfterSibilant:
    """Vowel swaps after ш, щ, ж, ч."""

    def test_o_to_yo(self):
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("Девчонка")]
        sentence = ["Девчонка"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "Девчёнка"

    def test_yo_to_o(self):
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("шёвинист")]
        sentence = ["шёвинист"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "шовинист"

    def test_yu_swap_removed(self):
        """ю↔у swap was removed — only applies to 3 loanwords, produces чюдо/шютка."""
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("жюри")]
        sentence = ["жюри"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        # Should not swap — ю↔у removed from sibilant swaps
        assert result is None or sentence[0] == "жюри"

    def test_yo_to_o_sibilant(self):
        """ё→о after sibilant still works."""
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("щётка")]
        sentence = ["щётка"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "щотка"

    def test_propn_surname_not_swapped(self):
        """Audit bug B8 (ortho scope): Шолохов is a surname whose spelling
        is lexicalized — Шолохов → Шёлохов is not a real spelling error.
        PROPN tokens must be excluded from this subtype."""
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("Шолохов", pos="PROPN")]
        sentence = ["Шолохов"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "Шолохов"


class TestRootVowelAfterSibilant:
    """и/ы after ц in ROOTS (§7) — root-position complement of vowel_after_ts."""

    def test_regular_root_i_to_y(self):
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цирк")]
        sentence = ["цирк"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "цырк"
        assert result.error_type == "orthographic_spelling_root_vowel_after_sibilant"

    def test_regular_root_i_to_y_cifra(self):
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цифра")]
        sentence = ["цифра"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "цыфра"

    def test_preserves_case(self):
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("Цирк")]
        sentence = ["Цирк"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "Цырк"

    def test_exception_tsygan_family_y_to_i(self):
        """цыганский: ы is correct, error introduces и.

        (The bare noun цыган/цыганка are skipped by the known-word guard —
        pymorphy recognizes "циган"/"циганка" as attested spellings — but
        derived forms like цыганский are not, so this is the clean example
        for the цыган family.)
        """
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цыганский", pos="ADJ")]
        sentence = ["цыганский"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "циганский"

    def test_exception_tsyplyonok_family(self):
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цыплёнок")]
        sentence = ["цыплёнок"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "циплёнок"

    def test_exception_tsypochki_family(self):
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цыпочки")]
        sentence = ["цыпочки"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "ципочки"

    def test_exception_tsyts_family(self):
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цыц", pos="INTJ")]
        sentence = ["цыц"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "циц"

    def test_exception_tsykat_family(self):
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цыкать", pos="VERB")]
        sentence = ["цыкать"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "цикать"

    def test_suffix_position_not_swapped(self):
        """лисица has ц+и at a SUFFIX boundary (лис-иц-а), not root — this
        is vowel_after_ts / suffix_its_ets territory, not ours."""
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("лисица")]
        sentence = ["лисица"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "лисица"

    def test_suffix_position_not_swapped_ratsiya(self):
        """рация: ц+и is inside the -циj- suffix, not the root."""
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("рация")]
        sentence = ["рация"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "рация"

    def test_unsegmented_word_skipped(self):
        """Words absent from the unified-dict segmentation are skipped
        rather than guessed at (precision-first)."""
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("мерцы", lemma="мерцы")]  # synthetic OOV token
        sentence = ["мерцы"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "мерцы"

    def test_known_word_result_skipped(self, monkeypatch):
        """If the corrupted surface coincides with a real word, skip."""
        from synterr.languages.russian.resources import MorphemeAnalyzer

        monkeypatch.setattr(MorphemeAnalyzer, "word_is_known", lambda self, word: True)
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("цирк")]
        sentence = ["цирк"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "цирк"

    def test_propn_not_swapped(self):
        """Audit bug B8 (ortho scope): PROPN tokens are excluded from this
        subtype too — a ц+и/ы root pattern in a proper noun is lexicalized,
        not a spelling error candidate."""
        h = _force_subtype("root_vowel_after_sibilant")
        tokens = [_tok("Цирк", pos="PROPN")]
        sentence = ["Цирк"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "Цирк"


class TestAdjEndingVowel:
    """-ем/-им confusion in Ins/Loc singular soft-stem adjectives (§39)."""

    def _adj(self, text, case, gender="Neut", number="Sing"):
        return _tok(
            text,
            pos="ADJ",
            features={"Case": case, "Number": number, "Gender": gender},
        )

    def _adp(self, text):
        return _tok(text, pos="ADP")

    def test_loc_to_ins_dalnem(self):
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("в"), self._adj("дальнем", "Loc")]
        sentence = ["в", "дальнем"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence[1] == "дальним"

    def test_ins_to_loc_prezhnim(self):
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("с"), self._adj("прежним", "Ins")]
        sentence = ["с", "прежним"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence[1] == "прежнем"

    def test_loc_to_ins_sinem(self):
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("о"), self._adj("синем", "Loc")]
        sentence = ["о", "синем"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence[1] == "синим"

    def test_preserves_case(self):
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("в"), self._adj("Дальнем", "Loc")]
        sentence = ["в", "Дальнем"]
        h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert sentence[1] == "Дальним"

    def test_no_governing_preposition_skipped(self):
        """зимним утром: genuine Ins-of-time use with no preposition at
        all — the context is ambiguous per our guard, so we skip rather
        than risk mislabeling."""
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adj("зимним", "Ins"), _tok("утром")]
        sentence = ["зимним", "утром"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is None
        assert sentence[0] == "зимним"

    def test_preposition_two_tokens_away_still_fires(self):
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("о"), _tok("чём"), self._adj("синем", "Loc")]
        sentence = ["о", "чём", "синем"]
        result = h.apply(tokens, sentence, 2, set(), rng=Random(42))
        assert result is not None
        assert sentence[2] == "синим"

    def test_preposition_too_far_skipped(self):
        """4 tokens back is outside the 3-token window."""
        h = _force_subtype("adj_ending_vowel")
        tokens = [
            self._adp("о"),
            _tok("самом"),
            _tok("этом"),
            _tok("вот"),
            self._adj("синем", "Loc"),
        ]
        sentence = ["о", "самом", "этом", "вот", "синем"]
        result = h.apply(tokens, sentence, 4, set(), rng=Random(42))
        assert result is None
        assert sentence[4] == "синем"

    def test_mismatched_preposition_case_skipped(self):
        """с (Ins-governing) next to a Loc-tagged adjective: the guard
        requires the ADP's licensed case to match the token's own Case."""
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("с"), self._adj("синем", "Loc")]
        sentence = ["с", "синем"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is None
        assert sentence[1] == "синем"

    def test_feminine_skipped(self):
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("в"), self._adj("дальнем", "Loc", gender="Fem")]
        sentence = ["в", "дальнем"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is None

    def test_plural_skipped(self):
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("в"), self._adj("дальнем", "Loc", number="Plur")]
        sentence = ["в", "дальнем"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is None

    def test_hard_stem_not_matched(self):
        """новом (hard-stem Loc) doesn't end in -ем/-им — not this subtype."""
        h = _force_subtype("adj_ending_vowel")
        tokens = [self._adp("о"), self._adj("новом", "Loc")]
        sentence = ["о", "новом"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is None


class TestCanApplyEdgeCases:
    handler = OrthographicSpellingHandler()

    def test_non_alpha_rejected(self):
        tokens = [_tok(",", pos="PUNCT")]
        assert not self.handler.can_apply(tokens, 0)

    def test_short_word_rejected(self):
        tokens = [_tok("да", pos="PART")]
        assert not self.handler.can_apply(tokens, 0)

    def test_allcaps_abbreviation_rejected(self):
        """Audit fix O4: all-caps abbreviations (США, ФСБ, ГИБДД...) are
        skipped across the whole handler, not just individual subtypes."""
        tokens = [_tok("США", pos="PROPN")]
        assert not self.handler.can_apply(tokens, 0)

    def test_allcaps_abbreviation_with_nn_rejected(self):
        """ИНН contains "НН" — without the abbreviation gate this could
        tempt nn_suffix's textual candidacy check."""
        tokens = [_tok("ИНН", pos="PROPN")]
        assert not self.handler.can_apply(tokens, 0)


class TestEnabledSubtypes:
    """set_enabled_subtypes restricts which subtype apply() may emit."""

    def test_filter_emits_only_requested_subtype(self):
        """Ялтинский matches both suffix_insk_ensk and nn_suffix candidates.
        With only suffix_insk_ensk enabled, that is what must be emitted."""
        h = OrthographicSpellingHandler()
        h.set_enabled_subtypes({"suffix_insk_ensk"})
        for seed in range(10):
            sentence = ["Ялтинский"]
            result = h.apply(
                [_tok("Ялтинский", pos="ADJ")], sentence, 0, set(), rng=Random(seed)
            )
            assert result is not None
            assert result.error_type == "orthographic_spelling_suffix_insk_ensk"
            assert sentence[0] == "Ялтенский"

    def test_filter_other_subtype(self):
        h = OrthographicSpellingHandler()
        h.set_enabled_subtypes({"nn_suffix"})
        for seed in range(10):
            sentence = ["Ялтинский"]
            result = h.apply(
                [_tok("Ялтинский", pos="ADJ")], sentence, 0, set(), rng=Random(seed)
            )
            assert result is not None
            assert result.error_type == "orthographic_spelling_nn_suffix"

    def test_filter_returns_none_when_no_candidate_enabled(self):
        """керченский only offers suffix_insk_ensk; enabling an unrelated
        subtype must yield None rather than a mislabeled error."""
        h = OrthographicSpellingHandler()
        h.set_enabled_subtypes({"pre_pri"})
        sentence = ["керченский"]
        result = h.apply(
            [_tok("керченский", pos="ADJ")], sentence, 0, set(), rng=Random(0)
        )
        assert result is None
        assert sentence[0] == "керченский"

    def test_none_means_all(self):
        h = OrthographicSpellingHandler()
        h.set_enabled_subtypes({"pre_pri"})
        h.set_enabled_subtypes(None)
        assert h._enabled_subtypes is None

    def test_invalid_subtype_raises(self):
        h = OrthographicSpellingHandler()
        with pytest.raises(ValueError, match="Unknown subtypes"):
            h.set_enabled_subtypes({"not_a_subtype"})


# Compound adjectives whose dict segmentation carries an annotation
# character (the linking SUFF "о-", e.g. бел|о-|камен|н|ый) before the нн.
# Raw len() summing in resources.morpheme_at_char shifted every morpheme
# after the annotated one a character right, so the second н of нн read as
# ROOT and _is_suffix_boundary rejected a genuine §52 suffix-boundary
# target (~175 such adjectives; review finding 2026-07-12).
COMPOUND_NN_ADJECTIVES = [
    "белокаменный",
    "иностранный",
    "второстепенный",
    "благосклонный",
    "белокочанный",
]


class TestSurfaceAlignedMorphemeOffsets:
    """Regression tests for the surface-aligned morpheme offsets in
    resources.MorphemeAnalyzer (root fix behind the nn_suffix regression).
    """

    @pytest.mark.parametrize("word", COMPOUND_NN_ADJECTIVES)
    def test_nn_position_maps_to_root_suffix_boundary(self, word):
        """First н of нн is root-final, second н is the SUFF morpheme —
        exactly the boundary shape _is_suffix_boundary checks (last char
        of the matched span)."""
        from synterr.languages.russian.resources import get_morpheme_analyzer

        analyzer = get_morpheme_analyzer()
        nn_pos = word.find("нн")
        assert nn_pos > 0
        assert analyzer.char_in_morpheme_type(word, nn_pos, "ROOT") is True
        assert analyzer.char_in_morpheme_type(word, nn_pos + 1, "SUFF") is True

    @pytest.mark.parametrize("word", COMPOUND_NN_ADJECTIVES)
    def test_nn_suffix_fires_on_compound_adjectives(self, word):
        h = _force_subtype("nn_suffix")
        sentence = [word]
        result = h.apply([_tok(word, pos="ADJ")], sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == word.replace("нн", "н")

    def test_root_internal_nn_still_reads_as_root(self):
        """тоннельный: both н of нн live inside the loanword root — the
        prior true-negative must survive the offset change."""
        from synterr.languages.russian.resources import get_morpheme_analyzer

        analyzer = get_morpheme_analyzer()
        nn_pos = "тоннельный".find("нн")
        assert analyzer.char_in_morpheme_type("тоннельный", nn_pos, "ROOT") is True
        assert analyzer.char_in_morpheme_type("тоннельный", nn_pos + 1, "ROOT") is True

    def test_root_internal_in_still_reads_as_root(self):
        """алюминиевый: "ин" is root-internal (root "алюмин"), not the
        adjectival -ин- suffix — must still read ROOT at both chars."""
        from synterr.languages.russian.resources import get_morpheme_analyzer

        analyzer = get_morpheme_analyzer()
        in_pos = "алюминиевый".find("ин")
        assert analyzer.char_in_morpheme_type("алюминиевый", in_pos, "ROOT") is True
        assert analyzer.char_in_morpheme_type("алюминиевый", in_pos + 1, "ROOT") is True

    def test_misaligned_dict_entry_returns_unknown(self):
        """авторизованный stores the infinitive's morphemes (…ова|ть) —
        beyond the shared stem the spans can't be trusted. The stem spans
        still verify; the diverging tail is dropped (END fallthrough)."""
        from synterr.languages.russian.resources import get_morpheme_analyzer

        analyzer = get_morpheme_analyzer()
        spans = analyzer.surface_morpheme_spans("авторизованный")
        assert spans is not None
        covered = spans[-1][0] + len(spans[-1][1])
        assert "".join(t for _, t, _ in spans) == "авторизованный"[:covered]

    def test_truncated_dict_entry_keeps_stem_spans(self):
        """цыпочки stores the singular's morphemes (ending "а"): stem spans
        up to the divergence are kept, the surface ending falls through to
        END — the entry must not go fully unknown."""
        from synterr.languages.russian.resources import get_morpheme_analyzer

        analyzer = get_morpheme_analyzer()
        assert analyzer.morpheme_at_char("цыпочки", 0) == ("цып", "ROOT")
        assert analyzer.morpheme_at_char("цыпочки", 6) == ("и", "END")


@pytest.mark.slow
class TestNnSuffixCompoundAdjectivesRealPipeline:
    """The regressed compound adjectives must fire end-to-end through
    ErrorPipeline on real sentences, not just on fake-token fixtures."""

    @pytest.fixture(scope="class")
    def pipeline(self):
        from synterr.core.pipeline import ErrorPipeline, GenerationConfig
        from synterr.core.registry import get_language

        return ErrorPipeline(get_language("ru"), GenerationConfig(seed=42))

    @pytest.mark.parametrize(
        ("sentence", "word"),
        [
            ("Мы вошли в белокаменный собор.", "белокаменный"),
            ("Иностранный студент выучил язык.", "иностранный"),
            ("Это был второстепенный вопрос.", "второстепенный"),
            ("Благосклонный отзыв обрадовал автора.", "благосклонный"),
            ("Белокочанный салат стоял на столе.", "белокочанный"),
        ],
    )
    def test_nn_suffix_fires_through_pipeline(self, pipeline, sentence, word):
        result = pipeline.apply_error(sentence, "orthographic_spelling:nn_suffix")
        assert result is not None
        assert result.errors[0].error_type == "orthographic_spelling_nn_suffix"
        # Sentence-initial adjectives keep their capitalization in the output.
        expected = word.replace("нн", "н")
        assert any(t.lower() == expected for t in result.corrupted_tokens)
