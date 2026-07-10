"""Russian lexical error handlers - paronyms, ..."""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken, ErrorResult
from synterr.languages.russian.errors.morphological import (
    _get_pymorphy_parse,
    inflect_word,
)
from synterr.languages.russian.inflector import (
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_NUMBER,
    match_capitalization,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

# Groups whose key starts with this prefix are directed confusions: only the
# first member may be corrupted (e.g. чем→как is an attested error, but
# как→чем is garbage no learner produces).
_DIRECTED_PREFIX = "directed_"


def _confusion_candidates(group_key: str, members: list[str], word: str) -> list[str]:
    """Single-token replacement candidates for ``word`` within one group.

    Returns [] when the word is not a valid corruption source in this group
    (absent, or a non-head member of a directed group). Multi-word entries are
    never offered: a length-preserving $REPLACE cannot emit an intra-token
    space without misaligning the token/tag stream.
    """
    if group_key.startswith(_DIRECTED_PREFIX):
        if word != members[0]:
            return []
        pool = members[1:]
    else:
        if word not in members:
            return []
        pool = members
    return [x for x in pool if x != word and " " not in x]


def _all_confusion_candidates(groups: dict[str, list[str]], word: str) -> list[str]:
    """Union of candidates across every group containing ``word``.

    Collecting from all groups (instead of breaking at the first match)
    means JSON dict ordering can never decide which sense of a polysemous
    word gets corrupted.
    """
    candidates: list[str] = []
    for key, members in groups.items():
        for candidate in _confusion_candidates(key, members, word):
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _has_confusion(groups: dict[str, list[str]], word: str) -> bool:
    return bool(_all_confusion_candidates(groups, word))


def _pick_confusion(groups: dict[str, list[str]], word: str, rng: Random) -> str | None:
    candidates = _all_confusion_candidates(groups, word)
    if candidates:
        return rng.choice(candidates)
    return None


# UD features whose pymorphy equivalents must survive a paronym swap intact:
# transferring an undisambiguated parse's case/gender/number stacks a spurious
# agreement error on top of the intended Lex error.
_UD_FEATURE_MAPS = (
    ("Case", UD_TO_PYMORPHY_CASE),
    ("Number", UD_TO_PYMORPHY_NUMBER),
    ("Gender", UD_TO_PYMORPHY_GENDER),
)


def _context_grammemes(token: AnalyzedToken) -> set[str]:
    """pymorphy grammemes implied by stanza's disambiguated features."""
    wanted: set[str] = set()
    for feature, mapping in _UD_FEATURE_MAPS:
        value = token.features.get(feature)
        grammeme = mapping.get(value) if value is not None else None
        if grammeme:
            wanted.add(grammeme)
    return wanted


# Grammemes that may be transferred from the original word's parse to the
# paronym replacement: POS class plus form-level (inflectional) values.
# Lexeme-level grammemes (Qual, aspect, transitivity, animacy) must stay
# behind — the partner lexeme often lacks them, which would make inflection
# fail spuriously (e.g. практичный is Qual but практический is not).
_TRANSFER_POS = {
    "NOUN",
    "ADJF",
    "ADJS",
    "COMP",
    "VERB",
    "INFN",
    "PRTF",
    "PRTS",
    "GRND",
    "NUMR",
    "ADVB",
}
_TRANSFER_FORM = {
    "nomn",
    "gent",
    "datv",
    "accs",
    "ablt",
    "loct",
    "voct",
    "gen2",
    "loc2",
    "sing",
    "plur",
    "masc",
    "femn",
    "neut",
    "1per",
    "2per",
    "3per",
    "past",
    "pres",
    "futr",
    "actv",
    "pssv",
    "indc",
    "impr",
}
_ANIMACY = {"anim", "inan"}


def _transfer_grammemes(parse) -> set[str]:
    """Form-level grammemes to carry over to the paronym replacement."""
    grammemes = set(parse.tag.grammemes)
    transfer = grammemes & (_TRANSFER_POS | _TRANSFER_FORM)
    if "accs" in transfer:
        # Accusative surface form depends on animacy; without it pymorphy
        # would pick an arbitrary anim/inan variant.
        transfer |= grammemes & _ANIMACY
    return transfer


class ParonymErrorHandler:
    """Replace word from paronyms list to one from its paronyms"""

    name = "paronym"
    subtypes = ["paronym"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._paronyms = None
        self.__morph = None

    @property
    def _morph(self):
        if self.__morph is None:
            from synterr.languages.russian.resources import get_morph_analyzer

            self.__morph = get_morph_analyzer()
        return self.__morph

    @property
    def paronyms(self):
        if self._paronyms is None:
            from synterr.languages.russian.resources import get_paronyms

            self._paronyms = get_paronyms()
        return self._paronyms

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return tokens[idx].lemma in self.paronyms

    def _disambiguated_parse(self, token: AnalyzedToken, word: str):
        """Pick a pymorphy parse consistent with stanza's features.

        The stored ``pymorphy_parse`` is context-free (e.g. 'цветной' ->
        ADJF femn,sing,gent), so blindly transferring its grammemes breaks
        agreement ('цветной телевизор' -> 'цветастой телевизор'). Trust
        stanza's disambiguation: keep the stored parse only if it carries
        every case/number/gender grammeme stanza assigned, otherwise re-pick
        from all parses; if none is consistent, skip rather than guess.
        """
        parse = _get_pymorphy_parse(token)
        wanted = _context_grammemes(token)
        if not wanted:
            return parse
        if parse is not None and wanted <= set(parse.tag.grammemes):
            return parse
        for candidate in self._morph.parse(word):
            if wanted <= set(candidate.tag.grammemes):
                return candidate
        return None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply paronym error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.lemma not in self.paronyms:
            return None

        parse = self._disambiguated_parse(token, word)
        if parse is None:
            return None

        grammemes = _transfer_grammemes(parse)
        if not grammemes:
            return None

        new_word_lemma = rng.choice(self.paronyms.get(token.lemma))
        new_word_parse = self._morph.parse(new_word_lemma)[0]
        new_word = inflect_word(new_word_parse, grammemes, word)
        if new_word is None:
            return None
        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# Cases each lexicon preposition governs *in the sense its confusion group
# covers* (UD case names). Rozental keeps preposition choice (§199) and case
# government (§200) apart: a swap is a clean Prep error only when original and
# replacement govern the governed noun's observed case. о/об are limited to
# the topic sense (+Loc) so the contact sense (удариться о камень, +Acc) never
# swaps to про; с is limited to the source sense (+Gen) so comitative с+Ins
# (гулял с другом) never swaps to из/от.
_PREP_GOVERNMENT: dict[str, set[str]] = {
    "в": {"Acc", "Loc"},
    "на": {"Acc", "Loc"},
    "из": {"Gen"},
    "с": {"Gen"},
    "от": {"Gen"},
    "о": {"Loc"},
    "об": {"Loc"},
    "обо": {"Loc"},
    "про": {"Acc"},
    "к": {"Dat"},
    "до": {"Gen"},
    "благодаря": {"Dat"},
    "из-за": {"Gen"},
    "по причине": {"Gen"},
}

# POS that terminate the rightward scan for the governed nominal: past them
# we are no longer inside this preposition's phrase.
_GOVERNED_SCAN_STOP_POS = {"PUNCT", "VERB", "ADP", "CCONJ", "SCONJ"}


def _governed_case(tokens: Sequence[AnalyzedToken], idx: int) -> str | None:
    """Case of the nominal governed by the ADP at ``idx``.

    With depparse enabled, the ADP's head *is* its complement (UD ``case``
    relation). Without it, fall back to the first Case-bearing token to the
    right: agreeing determiners/adjectives share the complement's case, so
    the first hit inside the phrase is reliable.
    """
    token = tokens[idx]
    head_idx = token.head_idx
    if head_idx is not None and 0 <= head_idx < len(tokens) and head_idx != idx:
        case = tokens[head_idx].get_feature("Case")
        if case:
            return case
    for other in tokens[idx + 1 : idx + 5]:
        if other.pos in _GOVERNED_SCAN_STOP_POS:
            break
        case = other.get_feature("Case")
        if case:
            return case
    return None


class PrepositionErrorHandler:
    """Replace preposition with an attested confusion from the same group.

    Groups in ``prepositions.json`` are *confusion* sets, not synonym sets:
    every swap must yield a genuine error (attested learner confusion like
    в/на, из/с, or a different-government pair like благодаря/из-за where the
    unreinflected complement exposes the error). Synonymous prepositions with
    identical government (у ~ при ~ около ~ возле, через ~ сквозь — Rozental
    §199) are excluded: swapping them produces correct Russian, which would
    teach a GEC model to rewrite valid text.

    The handler is length-preserving (single ``$REPLACE``), so it only
    substitutes single-token replacements. Multi-word entries in the lexicon
    (e.g. ``"по причине"``) are skipped: writing one into a single token slot
    would smuggle an intra-token space into the GECToR unit and misalign the
    token/tag stream.

    Case government (Rozental §199 vs §200): a swap fires only when both the
    original and the replacement govern the case observed on the dependent
    noun. Different-government swaps (к+Dat -> до+Gen, благодаря+Dat ->
    из-за+Gen) would leave the unreinflected complement as a *second* error
    that RLC annotates Gov, not Prep — a mislabeled double error is worse
    than no error, so those candidates are skipped. When the governed case
    cannot be determined, the handler does not fire.
    """

    name = "preposition"
    subtypes = ["preposition"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._prepositions = None

    @property
    def prepositions(self):
        if self._prepositions is None:
            from synterr.languages.russian.resources import get_preposition_list

            self._prepositions = get_preposition_list()
        return self._prepositions

    def _candidates(
        self, tokens: Sequence[AnalyzedToken], idx: int, word: str
    ) -> list[str]:
        """Same-case-frame replacement candidates for the ADP at ``idx``."""
        case = _governed_case(tokens, idx)
        if case is None:
            return []
        if case not in _PREP_GOVERNMENT.get(word, set()):
            # Sense outside the lexicon's frames (e.g. comitative с+Ins) —
            # the confusion group does not apply here.
            return []
        return [
            candidate
            for candidate in _all_confusion_candidates(self.prepositions, word)
            if case in _PREP_GOVERNMENT.get(candidate, set())
        ]

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if tokens[idx].pos != "ADP":
            return False
        return bool(self._candidates(tokens, idx, tokens[idx].lemma))

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply preposition error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos != "ADP":
            return None

        candidates = self._candidates(tokens, idx, word.lower())
        if not candidates:
            return None
        new_word = rng.choice(candidates)

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# ---------------------------------------------------------------------------
# Pronoun confusion: shared dependency-tree "find the clause subject" walk.
#
# Both PronounSvoyErrorHandler (свой vs мой/твой/наш/ваш/его/её/их, §167) and
# PronounSebyaErrorHandler (себя/себе/собой vs personal pronouns, §168) need
# to identify the subject that the reflexive/possessive corefers with. That
# subject is found by climbing head_idx from a starting token until an
# nsubj/nsubj:pass dependent turns up.
# ---------------------------------------------------------------------------

# dep_rels marking a subordination/control boundary. Crossing one of these
# while climbing *without having found a local subject* risks resolving the
# wrong antecedent: control verbs assign an embedded infinitive's understood
# subject differently depending on the verb (просить = object control, хотеть
# = subject control), and relative/adverbial/complement/parataxis clauses
# routinely have a subject of their own that differs from the outer clause's.
# A local nsubj found *at* one of these nodes is still used (nearest-subject
# binding is correct); only climbing past one empty-handed is refused.
_CLAUSE_BOUNDARY_DEPRELS = {"xcomp", "acl", "acl:relcl", "advcl", "ccomp", "parataxis"}

# Bounds the climb so a malformed/cyclic parse can't loop forever.
_MAX_SUBJECT_WALK = 5

_SUBJECT_DEPRELS = ("nsubj", "nsubj:pass")

_FIRST_SECOND_PERSON_LEMMAS = {"я", "ты", "мы", "вы"}
_ALL_PERSONAL_PRONOUN_LEMMAS = {"я", "ты", "он", "она", "оно", "мы", "вы", "они"}


def _find_dependent_by_rel(
    tokens: Sequence[AnalyzedToken], head_idx: int, *dep_rels: str
) -> AnalyzedToken | None:
    """First token depending on head_idx via one of dep_rels."""
    for token in tokens:
        if token.head_idx == head_idx and token.dep_rel in dep_rels:
            return token
    return None


def _walk_up_for_subject(
    tokens: Sequence[AnalyzedToken], start_idx: int
) -> AnalyzedToken | None:
    """Nearest nsubj/nsubj:pass reachable by climbing head_idx from start_idx.

    Stops (returns None) on a clause-boundary dep_rel that has no local
    subject of its own, rather than inheriting a possibly-wrong outer one.
    """
    current: int | None = start_idx
    seen: set[int] = set()
    for _ in range(_MAX_SUBJECT_WALK):
        if current is None or current in seen or not (0 <= current < len(tokens)):
            return None
        seen.add(current)
        subject = _find_dependent_by_rel(tokens, current, *_SUBJECT_DEPRELS)
        if subject is not None:
            return subject
        head_tok = tokens[current]
        if head_tok.dep_rel in _CLAUSE_BOUNDARY_DEPRELS:
            return None
        if head_tok.head_idx is None or head_tok.head_idx == current:
            return None
        current = head_tok.head_idx
    return None


# UD Animacy -> pymorphy grammeme. свой/мой/твой/наш/ваш never carry Animacy
# themselves (only nouns do), but the masc-sing-Acc slot is animacy-ambiguous
# in pymorphy (моего vs мой), so it must be read off the noun being modified.
_UD_TO_PYMORPHY_ANIMACY = {"Anim": "anim", "Inan": "inan"}

# свой -> personal possessive, referent is 1st/2nd person: these decline like
# adjectives (мой, моя, моё, мои, моего, ...), so they go through pymorphy.
_SVOY_TO_PERSONAL_DECLINABLE = {"я": "мой", "ты": "твой", "мы": "наш", "вы": "ваш"}

# свой -> personal possessive, referent is 3rd person: его/её/их are frozen
# genitive forms of он/оно/она/они (pymorphy tags them ADJF,Fixd,Apro) and
# never inflect for the noun's case/number/gender, so no pymorphy call needed.
_SVOY_TO_PERSONAL_INVARIABLE = {"он": "его", "оно": "его", "она": "её", "они": "их"}

# Head nouns where свой is lexicalized/idiomatic rather than a productive
# reflexive-possessive slot: swapping in a personal possessive would not read
# as the target error, just as a broken idiom (не в своей тарелке, в своё
# время, на свой лад, идти своим чередом), so these are never corrupted.
_SVOY_IDIOM_HEAD_LEMMAS = {"тарелка", "время", "лад", "черёд", "очередь"}


def _svoy_subject(tokens: Sequence[AnalyzedToken], idx: int) -> AnalyzedToken | None:
    """Subject свой's referent must agree with, or None if undeterminable.

    With dep info: climb from the noun свой modifies (свой's own head) up to
    the clause subject. Two results are degenerate and rejected: the "subject"
    coming back as свой's own head noun (свой directly modifies the subject,
    e.g. "Своя рубашка ближе к телу" — no distinct external referent to
    borrow person/number from) or as свой itself (substantivized свой acting
    as the subject, e.g. "Свои всегда помогут" — nothing to corefer with).

    Without dep info: fall back to the nearest *preceding* 1st/2nd-person
    pronoun only. 3rd-person antecedents are excluded here because scanning
    "somewhere earlier in the sentence" for он/она/они without a parse is too
    likely to grab an unrelated referent; a bare я/ты/мы/вы is a much safer
    guess since Russian sentences rarely juggle more than one such speech-act
    participant.
    """
    token = tokens[idx]
    noun_idx = token.head_idx
    if noun_idx is not None and 0 <= noun_idx < len(tokens) and noun_idx != idx:
        subject = _walk_up_for_subject(tokens, noun_idx)
        if subject is None or subject.idx in (idx, noun_idx):
            return None
        return subject
    for i in range(idx - 1, -1, -1):
        if tokens[i].lemma in _FIRST_SECOND_PERSON_LEMMAS:
            return tokens[i]
    return None


class PronounSvoyErrorHandler:
    """свой -> personal possessive confusion (Rozental §167, RLC Ref).

    The textbook L2 error: a reflexive possessive whose referent is the
    clause subject gets replaced by a personal possessive agreeing with that
    same referent ("Я нашёл свою книгу" -> "Я нашёл мою книгу"). Only this
    direction (свой -> personal) is generated.

    The reverse direction (personal possessive -> свой) was deliberately not
    implemented. It only constitutes an error when the personal possessive is
    *not* coreferent with the subject ("Он взял его книгу" [чужую] -> "Он взял
    свою книгу" *changes what book is meant* rather than merely miscasing a
    reference) — detecting non-coreference reliably needs discourse-level
    entity tracking this handler has no access to (dep parse gives syntactic
    subjects, not discourse antecedents). Firing on ordinary "он ... его X"
    sentences where the possessor already is the subject (a redundant but
    common construction, itself sometimes flagged as the *same* §167 error in
    the other direction) would corrupt already-correct-enough text into a
    meaning change instead of a graded grammaticality error. Precision over
    recall: skip rather than guess at coreference.

    Guards: skips when no subject is determinable, when свой's own head noun
    is one of a small idiom list (§167 does not cover lexicalized свой), and
    when the target possessive fails to inflect (declinable branch only —
    его/её/их never inflect).
    """

    name = "pronoun_svoy"
    subtypes = ["pronoun_svoy"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self.__morph = None

    @property
    def _morph(self):
        if self.__morph is None:
            from synterr.languages.russian.resources import get_morph_analyzer

            self.__morph = get_morph_analyzer()
        return self.__morph

    def _apro_parse(self, lemma: str):
        """First pymorphy parse that is a declinable pronoun-adjective.

        'Fixd' parses (его/её/их as frozen possessives) are excluded here —
        they are handled via _SVOY_TO_PERSONAL_INVARIABLE and never reach
        this method — but excluding them defensively keeps this method
        honest about only returning something .inflect() can vary.
        """
        for parse in self._morph.parse(lemma):
            if "Apro" in parse.tag.grammemes and "Fixd" not in parse.tag.grammemes:
                return parse
        return None

    def _resolve(self, tokens: Sequence[AnalyzedToken], idx: int):
        """Plan the replacement, or None if the handler should not fire.

        Returns ("literal", word) for invariable его/её/их, or
        ("inflect", parse, grammemes) for declinable мой/твой/наш/ваш.
        """
        token = tokens[idx]
        if token.lemma != "свой" or token.pos not in ("DET", "PRON"):
            return None

        noun_idx = token.head_idx
        noun = (
            tokens[noun_idx]
            if noun_idx is not None and 0 <= noun_idx < len(tokens)
            else None
        )
        if noun is not None and noun.lemma in _SVOY_IDIOM_HEAD_LEMMAS:
            return None

        subject = _svoy_subject(tokens, idx)
        if subject is None:
            return None

        if subject.lemma in _SVOY_TO_PERSONAL_INVARIABLE:
            return ("literal", _SVOY_TO_PERSONAL_INVARIABLE[subject.lemma])

        if subject.lemma in _SVOY_TO_PERSONAL_DECLINABLE:
            target_lemma = _SVOY_TO_PERSONAL_DECLINABLE[subject.lemma]
        elif subject.pos in ("NOUN", "PROPN"):
            number = subject.get_feature("Number")
            gender = subject.get_feature("Gender")
            if number == "Plur":
                return ("literal", _SVOY_TO_PERSONAL_INVARIABLE["они"])
            if gender == "Fem":
                return ("literal", _SVOY_TO_PERSONAL_INVARIABLE["она"])
            if gender in ("Masc", "Neut"):
                return ("literal", _SVOY_TO_PERSONAL_INVARIABLE["он"])
            return None
        else:
            # Relative/interrogative/indefinite pronoun subject (который,
            # кто, ...) or anything else we can't map to a person/gender: no
            # reliable target, so skip rather than guess.
            return None

        grammemes = _context_grammemes(token)
        if not grammemes:
            return None
        # Animacy only disambiguates the Acc slot for masc-sing and plural;
        # fem/neut-sing Acc is unambiguous and pymorphy's .inflect() rejects
        # an anim/inan grammeme there outright (returns None), so it must not
        # be added except where it is actually needed.
        is_animacy_ambiguous_acc = "accs" in grammemes and (
            "plur" in grammemes or {"masc", "sing"} <= grammemes
        )
        if is_animacy_ambiguous_acc and noun is not None:
            animacy = _UD_TO_PYMORPHY_ANIMACY.get(noun.get_feature("Animacy"))
            if animacy:
                grammemes.add(animacy)
        parse = self._apro_parse(target_lemma)
        if parse is None:
            return None
        return ("inflect", parse, grammemes)

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._resolve(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply свой -> personal possessive error."""
        word = sentence[idx]

        plan = self._resolve(tokens, idx)
        if plan is None:
            return None

        if plan[0] == "literal":
            new_word_raw = plan[1]
        else:
            _, parse, grammemes = plan
            new_word_raw = inflect_word(parse, grammemes, word)
            if new_word_raw is None:
                return None

        new_word = match_capitalization(word, new_word_raw)
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# ---------------------------------------------------------------------------
# Pronoun confusion: reflexive себя/себе/собой -> personal pronoun (§168)
# ---------------------------------------------------------------------------


# Set phrases where себя/собой is lexicalized rather than a productive
# reflexive argument: swapping in a personal pronoun would not read as the
# target case-selection error, just as broken idiom. Checked by neighboring
# lemma (works identically with or without depparse) rather than a parse.
_SEBYA_FRAME_VERB_LEMMAS = frozenset(
    {
        "чувствовать",
        "почувствовать",
        "вести",
        "повести",
        "представлять",
        "представить",
        "позволить",
        "позволять",
        "мнить",
        "возомнить",
    }
)

_SEBYA_PREP_FRAME_VERBS = frozenset(
    {
        "принять",
        "принимать",
        "брать",
        "взять",
        "давать",
        "дать",
        "выйти",
        "выходить",
        "представлять",
        "представить",
        "знать",
    }
)


def _is_sebya_set_phrase(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    def lemma_at(i: int) -> str | None:
        return tokens[i].lemma if 0 <= i < len(tokens) else None

    prev1, prev2 = lemma_at(idx - 1), lemma_at(idx - 2)
    if prev1 == "так":  # так себе
        return True
    if prev1 == "сам":  # само собой (разумеется)
        return True
    if prev1 == "по" and prev2 == "сам":  # сам по себе
        return True
    if prev1 == "между":  # между собой
        return True
    if prev1 == "в" and prev2 in ("прийти", "приходить"):  # прийти/приходить в себя
        return True
    # Lexicalized predicate frames where себя is not a referential slot
    # (audit, 2026-07-07): чувствовать себя, вести себя, представлять
    # собой/из себя, принять/брать/взять на себя, позволить себе,
    # дать/давать знать о себе, выйти из себя.
    governor = None
    token = tokens[idx]
    if token.head_idx is not None and 0 <= token.head_idx < len(tokens):
        governor = tokens[token.head_idx]
    gov_lemma = (governor.lemma or "").lower() if governor is not None else ""
    if gov_lemma in _SEBYA_FRAME_VERB_LEMMAS:
        return True
    # preposition + себя frames: «на себя», «из себя», «о себе» governed by
    # a frame verb anywhere leftward in the clause
    if prev1 in ("на", "из", "о", "об") and gov_lemma in _SEBYA_PREP_FRAME_VERBS:
        return True
    if prev1 in ("на", "из", "о", "об"):
        for j in range(idx - 2, max(-1, idx - 6), -1):
            if (tokens[j].lemma or "").lower() in _SEBYA_PREP_FRAME_VERBS:
                return True
    return False


def _sebya_subject(tokens: Sequence[AnalyzedToken], idx: int) -> AnalyzedToken | None:
    """Subject себя's referent must agree with, or None if undeterminable.

    With dep info: себя/себе/собой attaches directly to its governing
    predicate (obj/iobj/obl), so the walk starts at that head_idx directly —
    no intermediate noun hop like свой needs. Degenerate self-reference
    (subject resolving to себя's own token — not reachable in practice since
    себя has no nominative form, kept as a defensive check) is rejected.

    Without dep info: fall back to a *clause-initial* personal pronoun only
    (position 0), not "somewhere earlier" — sentence-initial position is a
    strong subject signal under Russian's unmarked word order, which an
    arbitrary earlier pronoun is not.
    """
    token = tokens[idx]
    head_idx = token.head_idx
    if head_idx is not None and 0 <= head_idx < len(tokens) and head_idx != idx:
        subject = _walk_up_for_subject(tokens, head_idx)
        if subject is None or subject.idx == idx:
            return None
        return subject
    first = tokens[0] if tokens else None
    if (
        first is not None
        and first.idx != idx
        and first.lemma in _ALL_PERSONAL_PRONOUN_LEMMAS
    ):
        return first
    return None


class PronounSebyaErrorHandler:
    """Reflexive себя/себе/собой -> personal pronoun confusion (§168, RLC Ref).

    The textbook L2 error: a reflexive pronoun coreferent with the clause
    subject gets replaced by the personal pronoun matching that subject's
    person/number/gender ("Она довольна собой" -> "Она довольна ей/ею";
    "Он купил себе квартиру" -> "Он купил ему квартиру"). The replacement is
    inflected to себя's own case (Acc/Gen/Dat/Ins), carried over from the
    subject's person/number/gender — the same referent, wrong pronoun class.

    Guards: subject must be identifiable via the nsubj dep-tree arc (or, with
    no dep info, a clause-initial personal pronoun); a small set-phrase
    blocklist (так себе, само собой, сам по себе, между собой, прийти/
    приходить в себя) is excluded since себя there is lexicalized, not a
    referential slot; and a subject we can't map to person/gender (relative/
    interrogative/indefinite pronouns) skips rather than guesses.
    """

    name = "pronoun_sebya"
    subtypes = ["pronoun_sebya"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self.__morph = None

    @property
    def _morph(self):
        if self.__morph is None:
            from synterr.languages.russian.resources import get_morph_analyzer

            self.__morph = get_morph_analyzer()
        return self.__morph

    def _npro_parse(self, lemma: str):
        for parse in self._morph.parse(lemma):
            if "NPRO" in parse.tag.grammemes:
                return parse
        return None

    def _resolve(self, tokens: Sequence[AnalyzedToken], idx: int):
        """Plan the replacement (target_lemma, pymorphy_parse, grammemes),
        or None if the handler should not fire."""
        token = tokens[idx]
        if token.lemma != "себя" or token.pos != "PRON":
            return None
        if _is_sebya_set_phrase(tokens, idx):
            return None

        case = UD_TO_PYMORPHY_CASE.get(token.get_feature("Case"))
        if case is None:
            return None

        subject = _sebya_subject(tokens, idx)
        if subject is None:
            return None

        if subject.lemma in _ALL_PERSONAL_PRONOUN_LEMMAS:
            target_lemma = subject.lemma
        elif subject.pos in ("NOUN", "PROPN"):
            number = subject.get_feature("Number")
            gender = subject.get_feature("Gender")
            if number == "Plur":
                target_lemma = "они"
            elif gender == "Fem":
                target_lemma = "она"
            elif gender in ("Masc", "Neut"):
                target_lemma = "он"
            else:
                return None
        else:
            return None

        parse = self._npro_parse(target_lemma)
        if parse is None:
            return None
        return (parse, {case})

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._resolve(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply себя -> personal pronoun error."""
        word = sentence[idx]

        plan = self._resolve(tokens, idx)
        if plan is None:
            return None
        parse, grammemes = plan

        new_word_raw = inflect_word(parse, grammemes, word)
        if new_word_raw is None:
            return None
        new_word = match_capitalization(word, new_word_raw)
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


class ConjunctionErrorHandler:
    """Replace conjunction with an attested confusion from the same group.

    Groups in ``conjunctions.json`` are *confusion* sets, not synonym sets:
    pure synonyms (или ~ либо, и ~ да, хотя ~ хоть — equivalent variants in
    Rozental's rules on homogeneous members) are excluded because swapping
    them yields correct Russian. ``directed_*`` groups corrupt only their
    first member (чем→как is an attested error; как→чем is impossible).
    """

    name = "conjunction"
    subtypes = ["conjunction"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._conjunctions = None

    @property
    def conjunctions(self):
        if self._conjunctions is None:
            from synterr.languages.russian.resources import get_conjunction_list

            self._conjunctions = get_conjunction_list()
        return self._conjunctions

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if tokens[idx].pos not in ["CCONJ", "SCONJ"]:
            return False
        return _has_confusion(self.conjunctions, tokens[idx].lemma)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply conjunction error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos not in ["CCONJ", "SCONJ"]:
            return None

        new_word = _pick_confusion(self.conjunctions, word.lower(), rng)
        if new_word is None:
            return None

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# ---------------------------------------------------------------------------
# н-insertion/deletion on 3rd-person pronouns after prepositions (§169-170)
#
# Standard Russian augments the oblique forms of он/она/оно/они with a
# prothetic н- when (and only when) they are governed by a true preposition:
# "у него", "с ней", "к ним", "без неё". Without a governing preposition the
# bare forms are used: "его вижу", "ей нравится". The textbook L2 errors run
# in both directions:
#   (a) dropping the н after an ordinary preposition ("у него" -> "у его");
#   (b) hyper-correction: adding the н after one of a small closed class of
#       secondary/deverbative prepositions (благодаря, вопреки, согласно,
#       наперекор, навстречу) that take Dative but, exceptionally, never
#       trigger the augment ("благодаря ему" -> "благодаря нему").
# Both directions are pure surface-form swaps -- no inflection is needed,
# since the augmented and bare paradigms are just two fixed spellings of the
# same case/number/gender cell.
# ---------------------------------------------------------------------------

# Only он/она/оно/они (never я/ты/мы/вы) have an augmented paradigm.
_N_FORM_PRONOUN_LEMMAS = {"он", "она", "оно", "они"}

# Augmented (н-) surface form -> bare form, direction (a) source -> target.
# Loc forms (нём, and ней/них in the Loc cell) are deliberately excluded:
# Loc has no bare counterpart at all (it is only ever used after a
# preposition), so there is no competing "bare" spelling for a learner to
# confuse it with and this error pattern cannot arise there. Both ё and е
# spellings of the fem Gen/Acc form are covered since source corpora mix the
# two conventions.
_N_AUGMENTED_TO_BARE: dict[str, str] = {
    "него": "его",  # Gen/Acc masc/neut
    "неё": "её",  # Gen/Acc fem
    "нее": "ее",  # Gen/Acc fem, е-spelling
    "ней": "ей",  # Dat/Ins fem
    "нему": "ему",  # Dat masc/neut
    "них": "их",  # Gen/Acc plural
    "ним": "им",  # Ins masc/neut
    "ними": "ими",  # Ins plural
    "нею": "ею",  # Ins fem, alternative form
}

# Bare Dative surface form -> augmented form, direction (b). Restricted to
# Dative only: благодаря/вопреки/согласно/наперекор/навстречу all govern
# Dative (never Gen/Acc), so его/её/их are never a direction (b) candidate
# in the first place -- which is what keeps this direction safe from the
# possessive-determiner homonym (его/её/их as "his/her/their X"): those
# surface forms simply never appear in this dict, so there is nothing to
# guard against by exclusion. dep_rel is still checked defensively in
# _resolve in case a parser quirk ever tags a possessive as PRON.
_N_BARE_DATIVE_TO_AUGMENTED: dict[str, str] = {
    "ему": "нему",
    "ей": "ней",
    "им": "ним",
}

# Secondary/deverbative prepositions that exceptionally take the bare form.
_N_EXCEPTION_GOVERNOR_LEMMAS = {
    "благодаря",
    "вопреки",
    "согласно",
    "наперекор",
    "навстречу",
}


def _n_form_comparative_neighbor(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """True if the token to the left is a comparative-degree ADJ/ADV.

    "лучше него" / "лучше его" (better than him) are both acceptable -- the
    pronoun here is governed by the comparative itself (no true preposition
    is involved at all), so this is not the target error in either
    direction. In practice a comparative head is never tagged ADP, so the
    "governed by a true preposition" requirement in _resolve already
    excludes this construction; this check is kept as an explicit,
    parser-independent guard per spec.
    """
    if idx - 1 < 0:
        return False
    left = tokens[idx - 1]
    return left.pos in ("ADJ", "ADV") and left.get_feature("Degree") == "Cmp"


def _n_form_case_governor(
    tokens: Sequence[AnalyzedToken], idx: int
) -> AnalyzedToken | None:
    """Token governing tokens[idx] via the UD 'case' dependency relation.

    Adpositions (including secondary ones like благодаря) attach to their
    governed nominal with dep_rel='case' and head_idx pointing at that
    nominal -- so the governor is found by scanning for a token whose head
    is idx, not by looking at idx's own head_idx.
    """
    for other in tokens:
        if other.head_idx == idx and other.dep_rel == "case":
            return other
    return None


class PronounNFormErrorHandler:
    """3rd-person pronoun н-augment confusion after prepositions (§169-170,
    RLC Ref).

    Direction (a) -- drop н after an ordinary preposition: "у него" -> "у
    его", "с ней" -> "с ей", "к ним" -> "к им", "без неё" -> "без её". Fires
    only when a true preposition (any ADP attached via dep_rel='case', or --
    without depparse -- an ADP immediately to the left) governs the pronoun,
    and that governor is not one of the exception words below.

    Direction (b) -- hyper-correction after benefactive/adversative
    secondary prepositions that take Dative but never trigger the augment:
    благодаря, вопреки, согласно, наперекор, навстречу. "благодаря ему" ->
    "благодаря нему". Restricted to the bare Dative forms (ему/ей/им);
    checked by a plain lemma-adjacency scan (immediate left neighbor) since
    навстречу in particular is not reliably tagged ADP by the depparse
    backend (it is sometimes an ADV sibling of the pronoun rather than its
    dep_rel='case' head), so relying on the dep tree alone would miss it.

    Guards:
    - Only он/она/оно/они pronouns (PRON) participate; я/ты/мы/вы have no
      augmented paradigm.
    - Comparative degree left neighbor ("лучше него/его", both acceptable)
      is excluded in both directions.
    - Direction (a)'s augmented forms (него, неё, ней, нему, них, ним, ними,
      нею) are never used as the frozen possessive determiner (его/её/их
      only), so no possessive guard is needed there -- unambiguous by
      construction.
    - Direction (b) is restricted to the Dative-only bare forms (ему, ей,
      им); the possessive determiner его/её/их is a disjoint set of surface
      strings, so it is never a candidate, and dep_rel=='det' is checked
      defensively regardless.
    - Loc forms (нём, and the Loc cell of ней/них) are excluded from
      direction (a): Loc has no competing bare form at all (always requires
      a preposition), so this confusion cannot arise there.
    """

    name = "pronoun_n_form"
    subtypes = ["pronoun_n_form"]
    category = "OTHER"
    changes_length = False

    def _resolve(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[str, str] | None:
        """Plan the replacement as (direction, new_word), or None to skip."""
        token = tokens[idx]
        if token.pos != "PRON" or token.lemma not in _N_FORM_PRONOUN_LEMMAS:
            return None
        if _n_form_comparative_neighbor(tokens, idx):
            return None

        word_lower = token.text.lower()

        bare = _N_AUGMENTED_TO_BARE.get(word_lower)
        if bare is not None:
            # Loc cells (о ней, о них) have no bare counterpart in the
            # paradigm — dropping н there lands in a different case
            # (audit, 2026-07-07; the class docstring always promised this
            # guard). UD Case first, Loc-only prepositions as fallback.
            if token.get_feature("Case") == "Loc":
                return None
            governor = _n_form_case_governor(tokens, idx)
            if governor is None and idx - 1 >= 0 and tokens[idx - 1].pos == "ADP":
                governor = tokens[idx - 1]
            if governor is None or governor.lemma in _N_EXCEPTION_GOVERNOR_LEMMAS:
                return None
            if (governor.lemma or "").lower() in ("о", "об", "обо", "при"):
                return None
            return ("drop_n", bare)

        augmented = _N_BARE_DATIVE_TO_AUGMENTED.get(word_lower)
        if augmented is not None:
            if token.dep_rel == "det":
                return None
            if idx - 1 < 0 or tokens[idx - 1].lemma not in _N_EXCEPTION_GOVERNOR_LEMMAS:
                return None
            return ("add_n", augmented)

        return None

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._resolve(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply the н-form confusion."""
        word = sentence[idx]

        plan = self._resolve(tokens, idx)
        if plan is None:
            return None
        _, new_word_raw = plan

        new_word = match_capitalization(word, new_word_raw)
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
