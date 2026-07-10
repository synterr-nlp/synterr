from __future__ import annotations

from synterr.core.protocol import AnalyzedToken, ErrorHandler


class TestSpellingErrorHandler:
    """Tests for Russian spelling error handler."""

    def test_implements_protocol(self):
        """Test that handler implements ErrorHandler protocol."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "spelling"
        assert handler.category == "SPELL"
        assert handler.changes_length is False

    def test_can_apply(self):
        """Test can_apply checks for alphabetic tokens."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        tokens = [
            AnalyzedToken(text="книга", lemma="книга", pos="NOUN", features={}, idx=0),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(
                text="a", lemma="a", pos="X", features={}, idx=2
            ),  # too short
        ]

        assert handler.can_apply(tokens, 0) is True  # alphabetic, len >= 2
        assert handler.can_apply(tokens, 1) is False  # not alphabetic
        assert handler.can_apply(tokens, 2) is False  # too short

    def test_can_apply_skips_all_caps(self):
        """Audit fix S5(a): ALL-CAPS tokens of length >= 2 are skipped for
        every spelling subtype — МВД must never be corrupted to МВТ.
        Regression: prefix_voicing used to destroy all-caps casing on
        tokens like РАЗБИТЬ (see test_prefix_voicing_restores_allcaps).
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        tokens = [
            AnalyzedToken(text="МВД", lemma="мвд", pos="NOUN", features={}, idx=0),
            AnalyzedToken(
                text="РАЗБИТЬ", lemma="разбить", pos="VERB", features={}, idx=1
            ),
            AnalyzedToken(text="США", lemma="сша", pos="PROPN", features={}, idx=2),
            AnalyzedToken(text="книга", lemma="книга", pos="NOUN", features={}, idx=3),
            # A single capital letter (len 1) is not "all-caps" in any
            # meaningful sense — but can_apply already rejects len < 2.
            AnalyzedToken(text="Я", lemma="я", pos="PRON", features={}, idx=4),
        ]
        assert handler.can_apply(tokens, 0) is False
        assert handler.can_apply(tokens, 1) is False
        assert handler.can_apply(tokens, 2) is False
        assert handler.can_apply(tokens, 3) is True
        assert handler.can_apply(tokens, 4) is False  # len < 2 regardless

    def test_tsa_confusion(self):
        """Test тся/ться confusion errors."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        # Test ться → тся
        result = handler._tsa_confusion("учиться")
        assert result is not None
        assert result.corrupted == "учится"
        assert result.error_subtype == "tsa_confusion"

        # Test тся → ться
        result = handler._tsa_confusion("учится")
        assert result is not None
        assert result.corrupted == "учиться"

    def test_vowel_reduction(self):
        """Test vowel reduction errors."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._vowel_reduction("молоко")
        assert result is not None
        # Should change о to а or е to и
        assert result.corrupted != "молоко"
        assert result.error_subtype == "vowel_reduction"

    def test_keyboard_typo(self):
        """Test keyboard typo errors."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._keyboard_typo("книга")
        assert result is not None
        assert result.corrupted != "книга"
        assert len(result.corrupted) == len("книга")
        assert result.error_subtype == "keyboard"

    def test_prefix_voicing_skips_root_initial(self):
        """Root-initial из/ис/раз/... is not a prefix — no swap (§31 прим. 1).

        Regression: prefix_voicing used to produce non-words like *изтории,
        *разти, *восле by matching any word starting with a prefix string.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        root_initial = [
            ("искра", "искра"),
            ("история", "история"),
            ("истории", "история"),  # inflected → lemma fallback
            ("испанский", "испанский"),
            ("расти", "расти"),
            ("растения", "растение"),
            ("возле", "возле"),
            ("изюм", "изюм"),
            ("низина", "низина"),
            ("воск", "воск"),
        ]
        for word, lemma in root_initial:
            assert handler._prefix_voicing(word, lemma=lemma) is None, word

    def test_prefix_voicing_skips_unknown_words(self):
        """OOV words (not in morpheme dict) are skipped — can't verify prefix."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        assert handler._prefix_voicing("изквронт") is None

    def test_prefix_voicing_real_prefixes(self):
        """Genuine з-/с- prefixes still get the wrong-form swap."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("исправить", "исправить", "изправить"),
            ("разбить", "разбить", "расбить"),
            ("бесполезный", "бесполезный", "безполезный"),
            ("расписание", "расписание", "разписание"),
            ("разбили", "разбить", "расбили"),  # inflected → lemma fallback
        ]
        for word, lemma, expected in cases:
            result = handler._prefix_voicing(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected
            assert result.error_subtype == "prefix_voicing"

    def test_prefix_voicing_skips_before_vowel_and_hard_sign(self):
        """No з→с swap before vowels or ъ — voiced form is categorical there (§31).

        Regression: prefix_voicing used to produce *расузнать / *расъезд,
        modeling a devoicing that never happens before vowels.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("разузнать", "разузнать"),  # раз- is PREF, next char у (vowel)
            ("разъезд", "разъезд"),  # next char ъ
            ("разахаться", "разахаться"),  # next char а (vowel)
        ]
        for word, lemma in cases:
            assert handler._prefix_voicing(word, lemma=lemma) is None, word

    def test_prefix_voicing_vz_vs_pair(self):
        """§31 lists воз-(вз-): the вз-/вс- pair generates errors too."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("вспомнить", "вспомнить", "взпомнить"),
            ("взлететь", "взлететь", "вслететь"),
        ]
        for word, lemma, expected in cases:
            result = handler._prefix_voicing(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected

        # вс/вз at the start of unprefixed words is not touched
        for word, lemma in [("всегда", "всегда"), ("вселенная", "вселенная")]:
            assert handler._prefix_voicing(word, lemma=lemma) is None, word

    def test_prefix_voicing_cheres_maps_to_cherez(self):
        """черес- swaps to modern через- (черезчур), never archaic чрез-."""
        from synterr.languages.russian.errors.spelling import (
            PREFIX_VOICELESS_TO_VOICED,
        )

        assert PREFIX_VOICELESS_TO_VOICED["черес"] == "через"

    def test_prefix_voicing_restores_allcaps(self):
        """Regression (audit B10/S7): РАЗБИТЬ→расБИТЬ — an ALL-CAPS token
        falls into prefix_voicing's case-mismatch fallback branch (neither
        exact nor .capitalize() matches), which used to produce a
        lowercase prefix glued onto the still-uppercase remainder. Fixed
        via _restore_allcaps: the whole result is re-uppercased when the
        source token was ALL-CAPS.

        can_apply's ALL-CAPS skip (audit fix S5a) already prevents this
        from firing through the normal pipeline — this test calls the
        private method directly (bypassing can_apply) as a defensive,
        belt-and-braces check on _prefix_voicing itself.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._prefix_voicing("РАЗБИТЬ", lemma="разбить")
        assert result is not None
        assert result.corrupted == "РАСБИТЬ"
        assert result.corrupted.isupper()

        result = handler._prefix_voicing("ИСПРАВИТЬ", lemma="исправить")
        assert result is not None
        assert result.corrupted == "ИЗПРАВИТЬ"
        assert result.corrupted.isupper()

    def test_cluster_skips_word_initial_ssh(self):
        """Word-initial сш is prefix с- + root (§32) — deleting с yields a real
        verb of different aspect (сшить → шить), a non-error.

        Regression: cluster turned 'Она решила сшить платье' into perfectly
        grammatical 'Она решила шить платье'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._cluster("сшить") is None
        assert handler._cluster("сшил") is None
        assert handler._cluster("Сшить") is None

        # Word-internal сш still produces a non-word error
        result = handler._cluster("высший")
        assert result is not None
        assert result.corrupted == "выший"

    def test_cluster_rejects_real_word_results(self):
        """Cluster output that is itself a known word is a non-error: костный
        → косный ('inert') would be a grammatical substitution."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._cluster("костный") is None
        # Normal cases still fire (results are non-words)
        assert handler._cluster("счастье").corrupted == "щастье"
        assert handler._cluster("честный").corrupted == "чесный"

    def test_soft_sign_rejects_real_word_results(self):
        """ь deletion must not yield a known word — мать→мат, быть→быт etc.
        are grammatical sentences, not errors.

        Regression: 'Мать всегда поможет' became 'Мат всегда поможет'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        for word in ["мать", "быть", "весь", "есть", "уголь", "пыль", "ель"]:
            assert handler._soft_sign(word) is None, word

        # учиться→учится is a known word AND would duplicate tsa_confusion
        assert handler._soft_sign("учиться") is None

    def test_soft_sign_still_fires_on_nonword_results(self):
        """Genuine ь omissions (results are non-words) still generate."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("помощь", "помощ"),
            ("делаешь", "делаеш"),
            ("только", "толко"),
            ("письмо", "писмо"),
            ("подъезд", "подьезд"),  # ъ→ь branch
        ]
        for word, expected in cases:
            result = handler._soft_sign(word)
            assert result is not None, word
            assert result.corrupted == expected
            assert result.error_subtype == "soft_sign"

    def test_double_consonant_skips_suffix_nn(self):
        """Suffix -нн- (participles/adjectives) is §52 territory, owned by
        orthographic_spelling:nn_suffix — double_consonant (mapped to root
        doubles, §9) must not fire on it.

        Regression: 'Сделанная работа' → 'Сделаная работа' tagged as a root
        double.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        suffix_nn = [
            ("сделанная", "сделанный"),
            ("длинный", "длинный"),
            ("осенний", "осенний"),
        ]
        for word, lemma in suffix_nn:
            assert handler._double_consonant(word, lemma=lemma) is None, word

    def test_double_consonant_root_doubles_still_fire(self):
        """Root-internal doubles (§9) keep generating: масса, аппарат, коллега.

        Regression note: this used to test ванна→вана, but "вана" is itself
        a known dictionary word (genitive of the geographic name "Ван"/Lake
        Van per pymorphy3), so audit fix S6 now correctly rejects it — see
        test_double_consonant_rejects_real_word_results below.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("масса", "масса", "маса"),  # root-internal нн
            ("массу", "масса", "масу"),  # inflected → lemma fallback
            ("аппарат", "аппарат", "апарат"),
            ("коллега", "коллега", "колега"),
        ]
        for word, lemma, expected in cases:
            result = handler._double_consonant(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected
            assert result.error_subtype == "double_consonant"

    def test_double_consonant_rejects_real_word_results(self):
        """Audit fix S6: results that are themselves known words are
        rejected — "тонна" (ton) → "тона" is real (nom. plural of "тон"
        'shade'), and "ванна" (bathtub) → "вана" is real (genitive of the
        geographic name "Ван"/Lake Van per pymorphy3) — both grammatical,
        not misspellings.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._double_consonant("тонна", lemma="тонна") is None
        assert handler._double_consonant("ванна", lemma="ванна") is None

    def test_vowel_reduction_skips_stress_homographs(self):
        """Stress homographs (замо́к/за́мок) have one stress-dict reading; the
        other reading's STRESSED vowel would be corrupted, violating §1
        (reduction is unstressed-only).

        Regression: 'Тяжёлый замок висел на двери' → 'замак'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        for word in ["замок", "Замок", "мука", "орган", "дорогой", "хлопок"]:
            assert handler._vowel_reduction(word) is None, word

        # Unambiguous words still reduce
        assert handler._vowel_reduction("молоко") is not None

    def test_vowel_reduction_rejects_real_word_results(self):
        """Regression (audit B9/S6): "бывший" (former), и->е reduced,
        yields "бывшей" (a real inflected form of "бывшая"), a grammatical
        sentence, not a misspelling — must be rejected via the same
        known-word helper root_alternating already uses.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._vowel_reduction("бывший") is None

    def test_corrupt_first_draw_respects_weights(self):
        """The first sampled subtype is a true weighted draw, so when all
        enabled subtypes apply, emission fractions track configured weights.

        Regression: the old weighted shuffle gave keyboard ~0.17 instead of
        the configured 0.25 in this setup (fallback reshaping distribution).
        """
        from random import Random

        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        handler.set_enabled_subtypes({"tsa_confusion", "keyboard"})
        handler.set_subtype_weights({"tsa_confusion": 75, "keyboard": 25})

        rng = Random(42)
        n = 600
        counts = {"tsa_confusion": 0, "keyboard": 0}
        # Both subtypes always apply to "учится", so no fallback occurs and
        # emission == first draw.
        for _ in range(n):
            result = handler._corrupt("учится", rng)
            counts[result.error_subtype] += 1

        keyboard_frac = counts["keyboard"] / n
        assert 0.21 < keyboard_frac < 0.29, counts

    def test_corrupt_falls_back_when_first_draw_inapplicable(self):
        """If the drawn subtype can't apply, remaining methods still cascade."""
        from random import Random

        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        # vowel_reduction can never apply to an OOV word (no stress entry);
        # keyboard always can.
        handler.set_enabled_subtypes({"vowel_reduction", "keyboard"})
        handler.set_subtype_weights({"vowel_reduction": 99, "keyboard": 1})

        rng = Random(7)
        for _ in range(20):
            result = handler._corrupt("брзкворт", rng)
            assert result is not None
            assert result.error_subtype == "keyboard"

    # -------------------------------------------------------------------
    # root_alternating (§3)
    # -------------------------------------------------------------------

    def test_root_alternating_fires_on_positives(self):
        """Alternating-root swaps produce the naive vowel-only confusion.

        лаг/лож and раст/рос swap ONLY the vowel (предлагать → предлогать,
        растение → ростение), not the "correct" other allomorph
        (предложать/росение) — that mirrors the actual learner error of
        guessing the wrong vowel while keeping the surrounding consonants.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("загорать", "загорать", "загарать"),
            ("предлагать", "предлагать", "предлогать"),
            ("касаться", "касаться", "косаться"),
            ("растение", "растение", "ростение"),
            ("собирать", "собирать", "соберать"),
            ("выбирать", "выбирать", "выберать"),
            ("замирать", "замирать", "замерать"),
            ("вычитать", "вычитать", "вычетать"),
        ]
        for word, lemma, expected in cases:
            result = handler._root_alternating(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected, word
            assert result.error_subtype == "root_alternating"

    def test_root_alternating_preserves_capitalization(self):
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._root_alternating("Растение", lemma="растение")
        assert result is not None
        assert result.corrupted == "Ростение"

        result = handler._root_alternating("РАСТЕНИЕ", lemma="растение")
        assert result is not None
        assert result.corrupted == "РОСТЕНИЕ"

    def test_root_alternating_skips_stressed_vowel(self):
        """The stress-conditioned pairs (гар/гор etc.) only confuse the
        UNSTRESSED alternant — a stressed occurrence is definitionally
        correct, so no confusion is possible there (mirrors
        vowel_reduction's own stressed-vowel skip).

        Regression: 'загар' (stressed а, §3 correct) must not become
        'загор'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        for word, lemma in [("загар", "загар"), ("вплавить", "вплавить")]:
            assert handler._root_alternating(word, lemma=lemma) is None, word

    def test_root_alternating_skips_standalone_lexeme(self):
        """мир/пир/тир are unrelated standalone nouns that happen to spell
        like the мер/пер/тер~мир/пир/тир verb root — not this alternation.

        Regression: 'мир' (peace/world) must not become 'мер'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        for word in ["мир", "пир", "тир"]:
            assert handler._root_alternating(word, lemma=word) is None, word

    def test_root_alternating_rejects_real_word_results(self):
        """мак/мок is meaning-conditioned (dip vs. soak) — both forms are
        often real words, so the swap must be rejected when it lands on one.

        'обмакнуть' (dip) → swapping а→о yields 'обмокнуть' (soak), a real
        word with a different meaning, not a misspelling.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._root_alternating("обмакнуть", lemma="обмакнуть") is None

    def test_root_alternating_no_stress_check_needed_for_suffix_group(self):
        """бер/бир-type pairs are suffix-а--conditioned, not stress-based —
        no stress lookup is required (unlike гар/гор etc.). An OOV word
        (no stress_dict entry) still fires for this group."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        # "запирать" IS in the stress dict, but the point is stress_checked
        # is False for this family — verify via an unstressed-vs-stressed
        # sanity: the swap fires without needing a stress lookup at all.
        result = handler._root_alternating("запирать", lemma="запирать")
        assert result is not None
        assert result.corrupted == "заперать"

    def test_root_alternating_skips_unsegmented_words(self):
        """Words absent from the morpheme dict (no segmentation) are
        skipped — can't verify the ROOT morpheme."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._root_alternating("бгзкворт", lemma="бгзкворт") is None

    # -------------------------------------------------------------------
    # root_alternating: audit fix S1 (surface-aligned morpheme offsets)
    # -------------------------------------------------------------------

    def test_root_alternating_surface_aligned_offset_across_link_suffix(self):
        """Regression (audit B1): "высокогорный" segments as высок|о-|гор|н|ый
        — the SUFF "о-" interfix carries an annotation '-' that is not part
        of the surface spelling. Summing raw len(text) over morphemes
        inflated the offset by 1, landing the edit on 'р' (a consonant)
        instead of the root vowel 'о' — producing "высокогоаный".

        With the family denylist (audit fix S3, "высокогор*" in _GOR_DENY)
        this specific word no longer fires at all (it's the mountain root,
        unrelated to гореть) — verified separately below. This test instead
        confirms the underlying offset math via a non-denied word with the
        identical "root|о-interfix|ROOT" shape: "ветромер" (wind + о + mer,
        мер/мир family) must edit the actual root vowel, never a
        neighboring consonant.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._root_alternating("ветромер", lemma="ветромер")
        assert result is not None
        assert result.corrupted == "ветромир"
        # The edited character must be the root vowel (index 6: 'е' in
        # "мер"), never the interfix or a neighboring consonant.
        assert result.position == 6

        result = handler._root_alternating("водомер", lemma="водомер")
        assert result is not None
        assert result.corrupted == "водомир"

    def test_root_alternating_denies_mountain_family_despite_link_suffix(self):
        """Regression (audit B1 + B4/S3 combined): "высокогорный" must not
        fire at all — the surface-aligned offset now correctly identifies
        the root vowel, but "гор" here is the mountain root (гора), denied
        by the family-prefix entry "высокогор*" in _GOR_DENY.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._root_alternating("Высокогорный", lemma="высокогорный") is None

    def test_root_alternating_never_edits_outside_root_span(self):
        """Acceptance guard (audit fix S1): sweep a batch of known-good
        alternation words and assert the edited character always falls
        inside the actual matched root substring of the surface word.
        """
        from synterr.languages.russian.errors.spelling import (
            VOWELS,
            SpellingErrorHandler,
        )

        handler = SpellingErrorHandler()

        words = [
            ("загорать", "загорать"),
            ("предлагать", "предлагать"),
            ("касаться", "касаться"),
            ("растение", "растение"),
            ("собирать", "собирать"),
            ("замирать", "замирать"),
            ("вычитать", "вычитать"),
            ("ветромер", "ветромер"),
            ("наклонять", "наклонять"),
            ("творение", "творение"),
        ]
        for word, lemma in words:
            result = handler._root_alternating(word, lemma=lemma)
            if result is None:
                continue
            # The single edited character must differ from the original at
            # exactly one position, and that position must be a vowel in
            # the original word (never a consonant boundary artifact).
            assert word[result.position] in VOWELS, (word, result)

    # -------------------------------------------------------------------
    # root_alternating: audit fix S2 (клан/клон, твар/твор vowel index)
    # -------------------------------------------------------------------

    def test_root_alternations_validation_passes_at_import(self):
        """Audit fix S2: ROOT_ALTERNATIONS entries must index a VOWEL that
        differs between the two variants. клан/клон and твар/твор used to
        index 1 (the consonant л/в) instead of 2 (the vowel а/о) — the
        module-level _validate_root_alternations() (run at import) asserts
        this for every entry; re-running it here re-confirms the invariant.
        """
        from synterr.languages.russian.errors.spelling import (
            ROOT_ALTERNATIONS,
            VOWELS,
            _validate_root_alternations,
        )

        _validate_root_alternations()  # must not raise

        for (
            variant_a,
            variant_b,
            vowel_idx,
            _stress_checked,
            _denied,
        ) in ROOT_ALTERNATIONS:
            assert variant_a[vowel_idx] in VOWELS
            assert variant_b[vowel_idx] in VOWELS
            assert variant_a[vowel_idx] != variant_b[vowel_idx]

    def test_root_alternating_klan_klon_targets_vowel(self):
        """Regression (audit B5): клан/клон used to index 1 ('л', a
        consonant), so the swap was a silent no-op (corrupted == word).
        Fixed to index 2 (the vowel а/о) — "наклонять" (root "клон")
        must now corrupt to "накланять", editing the vowel, not 'л'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._root_alternating("наклонять", lemma="наклонять")
        assert result is not None
        assert result.corrupted == "накланять"
        assert result.original[result.position] == "о"  # edited char was the vowel

    def test_root_alternating_tvar_tvor_targets_vowel(self):
        """Regression (audit B5): твар/твор used to index 1 ('в', a
        consonant) — the vowel-index fix (idx 2) makes "творение" (root
        "твор") correctly corrupt to "тварение".
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._root_alternating("творение", lemma="творение")
        assert result is not None
        assert result.corrupted == "тварение"

    # -------------------------------------------------------------------
    # root_alternating: audit fix S3 (family-level denylists)
    # -------------------------------------------------------------------

    def test_root_alternating_denies_confirmed_leak_families(self):
        """Regression (audit B4): exact-lemma denylists let whole
        derivational families leak through one word at a time. Each of
        these was a confirmed leak in the coordinator's repro list; the
        family-prefix denylist entries (marked with a trailing '*' in the
        deny frozensets, matched via _lemma_denied) must block all of them.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("Читатель", "читатель"),  # leaked as чет/чит (читать unrelated)
            ("читателей", "читатель"),
            ("Косолапый", "косолапый"),  # leaked as кас/кос (коса unrelated)
            ("Оперативники", "оперативник"),  # leaked как пер/пир (loanword)
            ("вчетвером", "вчетвером"),  # leaked as чет/чит (numeral unrelated)
            ("Высокогорный", "высокогорный"),  # leaked as гар/гор (гора unrelated)
        ]
        for word, lemma in cases:
            assert handler._root_alternating(word, lemma=lemma) is None, word

        # "умиротворить" is a special case: the CONFIRMED leak was
        # "умиротворить"→"умеротворить" (мир/мер family matching the
        # unrelated "мир" 'peace' root — now denied via "умиротвор*" in
        # _MIR_DENY). But the word *also* contains a second, genuinely
        # alternating root — "твор" (create), which the audit fix S2 index
        # correction newly activates (клан/клон and твар/твор used to
        # index a consonant, making the swap a silent no-op). So
        # root_alternating now legitimately fires here via the твар/твор
        # family instead, producing "умиротварить" — a DIFFERENT, correct
        # corruption, not a residual leak. Assert the specific leaked
        # spelling never appears, without requiring the method return None.
        result = handler._root_alternating("умиротворить", lemma="умиротворить")
        if result is not None:
            assert result.corrupted != "умеротворить"
            assert result.corrupted == "умиротварить"

    def test_root_alternating_denies_500_sentence_leak_pass_findings(self):
        """Regression: additional homograph leaks surfaced by the required
        500(+)-sentence corpus pass over lenta_sents.txt with only
        root_alternating enabled — see spelling.py handler audit report for
        the full pass output. All are unrelated loanwords or proper-noun
        derivations that happen to share a ROOT string with an alternation
        family.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("перрона", "перрон"),  # loanword 'platform', unrelated to переть
            ("период", "период"),  # loanword, unrelated to переть
            ("таймеры", "таймер"),  # loanword 'timer', unrelated to мереть/мерить
            ("смертельно", "смертельно"),  # смерть noun, no -а- suffix context
            ("измерение", "измерение"),  # мерить (measure), unrelated to мереть
            ("пример", "пример"),  # мера (measure), unrelated to мереть
            ("размеров", "размер"),  # мера (measure), unrelated to мереть
            ("Фермер", "фермер"),  # loanword 'farmer', unrelated to мереть/мерить
            ("Косовский", "косовский"),  # placename adjective, unrelated to косить
            ("клонировать", "клонировать"),  # loanword 'clone', unrelated to клонять
            ("бернского", "бернский"),  # placename adjective, unrelated to брать
            ("контртеррористических", "контртеррористический"),  # loanword, bad seg
        ]
        for word, lemma in cases:
            assert handler._root_alternating(word, lemma=lemma) is None, word

    # -------------------------------------------------------------------
    # root_alternating: audit fix S5(b) — PROPN skip
    # -------------------------------------------------------------------

    def test_root_alternating_skips_propn(self):
        """Regression (audit B7/B8 scope, S5b): "Берлина" (city name,
        genitive) segments with ROOT "бер", colliding with the бер/бир
        alternation family — but proper nouns aren't subject to §3.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._root_alternating("Берлина", lemma="берлин", pos="PROPN") is None
        # Without a POS tag (or with a non-PROPN tag) the alternation still
        # fires — confirms the skip is POS-gated, not a blanket denial.
        result = handler._root_alternating("Берлина", lemma="берлин", pos=None)
        assert result is not None
        assert result.corrupted == "Бирлина"

    # -------------------------------------------------------------------
    # root_unchecked (§2)
    # -------------------------------------------------------------------

    def test_root_unchecked_fires_on_positives(self):
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            # винегрет repositioned by audit fix S4 (см.
            # test_root_unchecked_repositioned_link_and_suffix_entries):
            # the original pos targeted a LINK interfix vowel, not ROOT.
            ("винегрет", "винегрет", "венегрет"),
            ("корзина", "корзина", "карзина"),
            ("вокзал", "вокзал", "вакзал"),
            ("собака", "собака", "сабака"),
            ("карандаш", "карандаш", "корандаш"),
        ]
        for word, lemma, expected in cases:
            result = handler._root_unchecked(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected, word
            assert result.error_subtype == "root_unchecked"

    def test_root_unchecked_fires_on_inflected_forms(self):
        """Lookup is by lemma, but the substitution applies to the actual
        surface form (position stable across regular declension)."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._root_unchecked("корзины", lemma="корзина")
        assert result is not None
        assert result.corrupted == "карзины"

    def test_root_unchecked_preserves_capitalization(self):
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._root_unchecked("Собака", lemma="собака")
        assert result is not None
        assert result.corrupted == "Сабака"

    def test_root_unchecked_requires_lemma(self):
        """No lemma means the exact-lemma guard can't be checked — skip."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._root_unchecked("корзина", lemma=None) is None

    def test_root_unchecked_skips_words_not_in_lexicon(self):
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        for word in ["стол", "книга", "человек"]:
            assert handler._root_unchecked(word, lemma=word) is None, word

    def test_root_unchecked_skips_propn(self):
        """Audit fix S5(b): PROPN tokens skip root_unchecked even if the
        lemma happens to be present in the curated lexicon."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._root_unchecked("Собака", lemma="собака", pos="PROPN") is None
        result = handler._root_unchecked("Собака", lemma="собака", pos=None)
        assert result is not None

    def test_root_unchecked_repositioned_link_and_suffix_entries(self):
        """Regression (audit B7/S4): 5 entries in root_unchecked.json used
        to target non-ROOT positions per unified_dict segmentation —
        винегрет/велосипед/гардероб/калейдоскоп pointed at a LINK interfix
        vowel, and космонавт pointed at a SUFF interfix vowel. All 5 are
        repositioned to a genuinely root-internal, unstressed vowel.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("винегрет", "винегрет", "венегрет"),
            ("велосипед", "велосипед", "вилосипед"),
            ("гардероб", "гардероб", "гордероб"),
            ("калейдоскоп", "калейдоскоп", "колейдоскоп"),
            ("космонавт", "космонавт", "касмонавт"),
        ]
        for word, lemma, expected in cases:
            result = handler._root_unchecked(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected, word

    def test_root_unchecked_lexicon_entries_are_root_internal(self):
        """Acceptance guard (audit fix S4): every root_unchecked.json entry
        whose lemma has dict segmentation must position its vowel inside a
        ROOT morpheme. _validate_root_unchecked_lexicon runs automatically
        on first lexicon access (see _root_unchecked_lexicon); this test
        re-invokes it directly against the loaded lexicon so a regression
        fails loudly here rather than only via a lazy singleton.
        """
        from synterr.languages.russian.errors.spelling import (
            _root_unchecked_lexicon,
            _validate_root_unchecked_lexicon,
        )

        lexicon = _root_unchecked_lexicon()
        assert len(lexicon) > 0
        _validate_root_unchecked_lexicon(lexicon)  # must not raise
