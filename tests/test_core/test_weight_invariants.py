"""Weight-invariant tests: preset weights must actually drive generation.

Regression net for the "config not actually applied" bug class. Three
instances of it were found in one week (March 2026):

1. Length-changing handlers were drawn uniformly, ignoring preset weights.
2. The spelling handler's method cascade treated weight 0 as low-priority
   instead of excluded, so zeroed subtypes still fired as fallbacks.
3. CommaDeleteHandler had no ``set_subtype_weights``, so preset
   ``comma_delete`` subtype blocks were silently inert.

The invariants below make the whole class structurally hard to reintroduce:

* Every ``weights:`` key in every preset names a registered handler.
* Every ``subtype_weights:`` block in every preset targets a handler that
  implements ``set_subtype_weights`` and uses only valid subtype names.
* A handler configured with one positive subtype weight (all others zero)
  never emits an error of a zeroed subtype.
* The pipeline's weighted draw never returns a zero-weighted handler —
  including length-changing ones, and including the real lorugec preset.

Known violations found while writing these tests are marked xfail(strict)
with the bug named in the reason; see ``KNOWN_INERT_SUBTYPE_BLOCKS`` and
``ZERO_TOTAL_CRASH_HANDLERS``.
"""

from __future__ import annotations

import functools
import random
from pathlib import Path

import pytest

import synterr
from synterr.configs import load_preset
from synterr.core.pipeline import ErrorPipeline, GenerationConfig
from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors import get_all_handlers

# ── Preset / handler discovery ──────────────────────────────────────────────

PRESETS_DIR = Path(synterr.__file__).parent / "configs" / "russian"
PRESET_NAMES = sorted(p.stem for p in PRESETS_DIR.glob("*.yaml"))


@functools.cache
def _preset(name: str) -> dict:
    return load_preset("ru", name)


@functools.cache
def _handler_classes() -> dict[str, type]:
    return {h.name: type(h) for h in get_all_handlers()}


ALL_HANDLER_NAMES = sorted(_handler_classes())

# Multi-subtype handlers that accept per-subtype weights from presets.
WEIGHTED_MULTI_SUBTYPE = sorted(
    name
    for name, cls in _handler_classes().items()
    if len(cls.subtypes) > 1 and hasattr(cls, "set_subtype_weights")
)

# ── Known violations (exposed, not fixed — see module docstring) ────────────
# Both sets are empty: the violations found while writing this module
# (inert lorugec dash_delete block; ValueError on all-zero candidate
# weights in five handlers) were fixed the same day. The machinery stays
# so the next violation can be xfail-pinned instead of breaking CI.

KNOWN_INERT_SUBTYPE_BLOCKS: set[tuple[str, str]] = set()

ZERO_TOTAL_CRASH_HANDLERS: set[str] = set()


# ── Invariant 1: preset keys must bind to real handler machinery ────────────


def _subtype_block_params(with_inert_xfail: bool):
    params = []
    for preset in PRESET_NAMES:
        data = load_preset("ru", preset)
        for handler_name in sorted(data.get("subtype_weights") or {}):
            marks = []
            if with_inert_xfail and (preset, handler_name) in (
                KNOWN_INERT_SUBTYPE_BLOCKS
            ):
                marks = [
                    pytest.mark.xfail(
                        strict=True,
                        reason=(
                            f"BUG: {preset}.yaml configures subtype_weights."
                            f"{handler_name} but the handler has no "
                            "set_subtype_weights — the preset block is "
                            "silently inert (CommaDeleteHandler bug class)"
                        ),
                    )
                ]
            params.append(
                pytest.param(
                    preset,
                    handler_name,
                    id=f"{preset}-{handler_name}",
                    marks=marks,
                )
            )
    return params


class TestPresetKeysBindToHandlers:
    """Every name a preset mentions must reach real handler machinery."""

    @pytest.mark.parametrize("preset", PRESET_NAMES)
    def test_weight_keys_are_registered_handlers(self, preset):
        weights = _preset(preset).get("weights") or {}
        unknown = set(weights) - set(ALL_HANDLER_NAMES)
        assert not unknown, (
            f"preset '{preset}' has weights for unregistered handlers "
            f"{sorted(unknown)} — these weights are silently ignored"
        )

    @pytest.mark.parametrize(
        ("preset", "handler_name"), _subtype_block_params(with_inert_xfail=True)
    )
    def test_subtype_weight_blocks_reach_a_setter(self, preset, handler_name):
        handlers = _handler_classes()
        assert handler_name in handlers, (
            f"preset '{preset}' has a subtype_weights block for "
            f"'{handler_name}', which is not a registered handler"
        )
        assert hasattr(handlers[handler_name], "set_subtype_weights"), (
            f"preset '{preset}' has a subtype_weights block for "
            f"'{handler_name}', but the handler does not implement "
            "set_subtype_weights — the block is silently inert"
        )

    @pytest.mark.parametrize(
        ("preset", "handler_name"), _subtype_block_params(with_inert_xfail=False)
    )
    def test_subtype_weight_keys_are_valid_subtypes(self, preset, handler_name):
        """Setters silently drop unknown keys; catch preset typos here."""
        handlers = _handler_classes()
        if handler_name not in handlers:
            pytest.skip("covered by test_subtype_weight_blocks_reach_a_setter")
        block = _preset(preset)["subtype_weights"][handler_name]
        unknown = set(block) - set(handlers[handler_name].subtypes)
        assert not unknown, (
            f"preset '{preset}' subtype_weights.{handler_name} has unknown "
            f"subtypes {sorted(unknown)} — set_subtype_weights silently "
            "ignores them"
        )


# ── Invariant 2: zero subtype weight means excluded, not deprioritized ──────


def _tok(text, pos="NOUN", lemma=None, idx=0, dep_rel=None, head_idx=None, features=None):
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features=features or {},
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
    )


def _seq(*specs):
    """Build a token list from (text, pos) tuples or bare strings."""
    tokens = []
    for i, spec in enumerate(specs):
        if isinstance(spec, str):
            tokens.append(_tok(spec, idx=i))
        else:
            text, pos = spec
            tokens.append(_tok(text, pos, idx=i))
    return tokens


# Diverse mocked sentences. Each cluster is known to trigger at least the
# subtypes listed in EXPECTED_FIRED below (verified against handler tables;
# no NLP backend or network required).
BATTERY: list[list[AnalyzedToken]] = [
    # spelling: tsa_confusion / vowel_reduction / soft_sign / devoicing /
    # double_consonant / keyboard / prefix_voicing / cluster
    _seq(("Он", "PRON"), ("хочет", "VERB"), ("учиться", "VERB"), ("в", "ADP"), ("школе", "NOUN")),
    _seq(("молоко", "NOUN"), ("стоит", "VERB"), ("на", "ADP"), ("столе", "NOUN")),
    _seq(("весь", "DET"), ("класс", "NOUN"), ("пришёл", "VERB")),
    _seq(("сказка", "NOUN"), ("про", "ADP"), ("коньки", "NOUN")),
    _seq(("разжечь", "VERB"), ("огонь", "NOUN")),
    _seq(("испугать", "VERB"), ("лошадь", "NOUN")),
    _seq(("поздно", "ADV"), ("вышло", "VERB"), ("солнце", "NOUN")),
    _seq(("лестница", "NOUN"), ("на", "ADP"), ("сердце", "NOUN")),
    # function_spelling
    _seq(("Никого", "PRON"), ("не", "PART"), ("было", "VERB")),
    _seq(("зато", "CCONJ"), ("он", "PRON"), ("пришёл", "VERB")),
    _seq(("что", "SCONJ"), ("бы", "PART"), ("он", "PRON"), ("сказал", "VERB")),
    _seq(("не", "PART"), ("красивый", "ADJ"), ("дом", "NOUN")),
    _seq(("некрасивый", "ADJ"), ("дом", "NOUN")),
    _seq(("опять-таки", "ADV"), ("он", "PRON"), ("пришёл", "VERB")),
    _seq(("так", "ADV"), ("же", "PART"), ("как", "SCONJ"), ("раньше", "ADV")),
    # orthographic_spelling
    _seq(("прибежать", "VERB"), ("преувеличить", "VERB"), ("приоткрыть", "VERB")),
    _seq(("сыграть", "VERB"), ("матч", "NOUN")),
    _seq(("доченька", "NOUN"), ("спит", "VERB")),
    _seq(("сестринский", "ADJ"), ("нищенский", "ADJ"), ("пост", "NOUN")),
    _seq(("красавица", "NOUN"), ("улыбнулась", "VERB")),
    _seq(("ключик", "NOUN"), ("лежит", "VERB")),
    _seq(("огурцы", "NOUN"), ("лекция", "NOUN"), ("куцый", "ADJ")),
    _seq(("жизнь", "NOUN"), ("хороша", "ADJ")),
    _seq(("деревянный", "ADJ"), ("дом", "NOUN")),
    # compound_spelling
    _seq(("25-й", "ADJ"), ("км", "NOUN")),
    _seq(("пол-лимона", "NOUN"), ("сока", "NOUN")),
    _seq(("культурно-массовый", "ADJ"), ("сектор", "NOUN")),
    # adverb_spelling
    _seq(("Он", "PRON"), ("посмотрел", "VERB"), ("вверх", "ADV")),
    _seq(("Он", "PRON"), ("говорит", "VERB"), ("по-русски", "ADV")),
    _seq(("Он", "PRON"), ("пошёл", "VERB"), ("в", "ADP"), ("верх", "NOUN")),
    _seq(("сказал", "VERB"), ("по", "ADP"), ("русски", "ADV")),
    # dash_delete: subj_pred + connective (dash_other)
    [
        _tok("Москва", "PROPN", idx=0, dep_rel="nsubj", head_idx=2),
        _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
        _tok("столица", "NOUN", idx=2, dep_rel="root"),
    ],
    [
        _tok("поезд", "NOUN", idx=0, dep_rel="root"),
        _tok("Москва", "PROPN", idx=1, dep_rel="appos", head_idx=0),
        _tok("—", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
        _tok("Казань", "PROPN", idx=3, dep_rel="conj", head_idx=1),
    ],
    # comma_delete: subordinate (ccomp)
    [
        _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
        _tok("знал", "VERB", idx=1, dep_rel="root"),
        _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
        _tok("что", "SCONJ", idx=3, dep_rel="mark", head_idx=5),
        _tok("она", "PRON", idx=4, dep_rel="nsubj", head_idx=5),
        _tok("придёт", "VERB", idx=5, dep_rel="ccomp", head_idx=1),
    ],
    # comma_delete: compound (conj with subjects on both sides)
    [
        _tok("Солнце", "PROPN", idx=0, dep_rel="nsubj", head_idx=1),
        _tok("светило", "VERB", idx=1, dep_rel="root"),
        _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
        _tok("и", "CCONJ", idx=3, dep_rel="cc", head_idx=5),
        _tok("птицы", "NOUN", idx=4, dep_rel="nsubj", head_idx=5),
        _tok("пели", "VERB", idx=5, dep_rel="conj", head_idx=1),
    ],
    # comma_delete: homogeneous (conj, non-clausal)
    [
        _tok("Мама", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
        _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
        _tok("папа", "NOUN", idx=2, dep_rel="conj", head_idx=0),
        _tok("и", "CCONJ", idx=3, dep_rel="cc", head_idx=4),
        _tok("бабушка", "NOUN", idx=4, dep_rel="conj", head_idx=0),
        _tok("пришли", "VERB", idx=5, dep_rel="root"),
    ],
    # comma_delete: parenthetical (parataxis)
    [
        _tok("Конечно", "ADV", idx=0, dep_rel="parataxis", head_idx=3),
        _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
        _tok("он", "PRON", idx=2, dep_rel="nsubj", head_idx=3),
        _tok("придёт", "VERB", idx=3, dep_rel="root"),
    ],
    # comma_delete: isolation (acl participle)
    [
        _tok("Студент", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
        _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
        _tok(
            "читающий",
            "VERB",
            idx=2,
            dep_rel="acl",
            head_idx=0,
            features={"VerbForm": "Part"},
        ),
        _tok("книгу", "NOUN", idx=3, dep_rel="obj", head_idx=2),
        _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=2),
        _tok("ушёл", "VERB", idx=5, dep_rel="root"),
    ],
    # comma_delete: interjection
    [
        _tok("Ах", "INTJ", idx=0, dep_rel="discourse", head_idx=2),
        _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
        _tok("как", "ADV", idx=2, dep_rel="advmod", head_idx=3),
        _tok("красиво", "ADV", idx=3, dep_rel="root"),
    ],
    # comma_delete: response да/нет
    [
        _tok("Да", "PART", idx=0, dep_rel="discourse", head_idx=3),
        _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
        _tok("он", "PRON", idx=2, dep_rel="nsubj", head_idx=3),
        _tok("придёт", "VERB", idx=3, dep_rel="root"),
    ],
    # comma_delete: repeated word
    [
        _tok("Дождь", "NOUN", lemma="дождь", idx=0),
        _tok(",", "PUNCT", idx=1),
        _tok("дождь", "NOUN", lemma="дождь", idx=2),
        _tok("идёт", "VERB", idx=3),
    ],
    # comma_delete: asyndetic (conj arc, no CCONJ)
    [
        _tok("Шли", "VERB", idx=0, dep_rel="root"),
        _tok("дожди", "NOUN", idx=1, dep_rel="nsubj", head_idx=0),
        _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=4),
        _tok("дороги", "NOUN", idx=3, dep_rel="nsubj:pass", head_idx=4),
        _tok("размыло", "VERB", idx=4, dep_rel="conj", head_idx=0),
        _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=0),
    ],
    # comma_insert: appositive как
    _seq(("Он", "PRON"), ("работал", "VERB"), ("как", "SCONJ"), ("экономист", "NOUN")),
    # comma_insert: frozen phrase ни ... ни
    _seq(("ни", "PART"), ("слуху", "NOUN"), ("ни", "PART"), ("духу", "NOUN")),
    # comma_insert: adjacent conjunctions with correlative
    _seq(("и", "CCONJ"), ("когда", "SCONJ"), ("мы", "PRON"), ("пришли", "VERB"), ("то", "PART")),
]

# Subtypes the battery is known to trigger when solely enabled. Keeps the
# zero-weight exclusion test non-vacuous: if a refactor stops these from
# firing, the test fails instead of silently passing on zero emissions.
EXPECTED_FIRED: dict[str, set[str]] = {
    "spelling": {
        "vowel_reduction",
        "devoicing",
        "prefix_voicing",
        "tsa_confusion",
        "cluster",
        "double_consonant",
        "keyboard",
        "soft_sign",
    },
    "function_spelling": {
        "ne_attachment",
        "ne_detachment",
        "conjunction_split",
        "conjunction_merge",
        "taki_hyphen",
        "neg_pronoun_ne_ni",
    },
    "orthographic_spelling": {
        "pre_pri",
        "y_i_after_prefix",
        "suffix_enk_onk",
        "suffix_insk_ensk",
        "suffix_its_ets",
        "suffix_ek_ik",
        "participle_suffix",
        "vowel_after_ts",
        "vowel_after_sibilant",
        "nn_suffix",
    },
    "compound_spelling": {"num_dash", "pol_spelling", "compound_adj"},
    "adverb_spelling": {
        "adverb_solid_to_separate",
        "adverb_separate_to_solid",
        "adverb_hyphen_to_separate",
        "adverb_separate_to_hyphen",
    },
    "comma_delete": {
        "comma_subordinate",
        "comma_compound",
        "comma_parenthetical",
        "comma_isolation",
        "comma_homogeneous",
        "comma_interjection",
        "comma_response",
        "comma_repeated",
        "comma_asyndetic",
        # comma_vocative: no battery example yet
    },
    "comma_insert": {
        "comma_before_kak",
        "comma_in_set_phrase",
        "comma_between_conjunctions",
        # comma_in_indivisible / comma_clause_junction: no battery example yet
    },
    "dash_delete": {
        "dash_subj_pred",
        "dash_other",
        # dash_asyndetic / dash_apposition: no battery example yet
    },
}

_SWEEP_SEEDS = 8


def _normalize_subtype(handler_name: str, error_type: str, subtypes: list[str]) -> str:
    """Map an emitted error_type back to its subtype name."""
    prefix = handler_name + "_"
    if error_type.startswith(prefix) and error_type[len(prefix) :] in subtypes:
        return error_type[len(prefix) :]
    return error_type


@functools.cache
def _sweep(handler_name: str) -> tuple[frozenset, tuple, tuple]:
    """For each subtype: enable only it, apply across the battery.

    Returns (fired_subtypes, leaks, crashes) where leaks are emissions of a
    subtype other than the solely-enabled one, and crashes are exceptions
    raised by apply() when the enabled subtype was inapplicable.
    """
    cls = _handler_classes()[handler_name]
    subtypes = list(cls.subtypes)
    fired: set[str] = set()
    leaks: list[tuple] = []
    crashes: list[tuple] = []

    for enabled in subtypes:
        handler = cls()
        handler.set_subtype_weights(
            {s: (100.0 if s == enabled else 0.0) for s in subtypes}
        )
        for tokens in BATTERY:
            for idx in range(len(tokens)):
                if not handler.can_apply(tokens, idx):
                    continue
                for seed in range(_SWEEP_SEEDS):
                    sentence = [t.text for t in tokens]
                    rng = random.Random(1000 * seed + idx)
                    try:
                        result = handler.apply(tokens, sentence, idx, set(), rng=rng)
                    except ValueError as exc:
                        crashes.append((enabled, tokens[idx].text, str(exc)))
                        break
                    if result is None:
                        continue
                    subtype = _normalize_subtype(
                        handler_name, result.error_type, subtypes
                    )
                    if subtype == enabled:
                        fired.add(enabled)
                    else:
                        leaks.append((enabled, result.error_type, tokens[idx].text))

    return frozenset(fired), tuple(leaks), tuple(crashes)


class TestZeroSubtypeWeightMeansExcluded:
    """Bug 2/3 regression: zeroed subtypes must never fire, on any handler."""

    @pytest.mark.parametrize("handler_name", WEIGHTED_MULTI_SUBTYPE)
    def test_zeroed_subtypes_never_emitted(self, handler_name):
        _, leaks, _ = _sweep(handler_name)
        assert not leaks, (
            f"{handler_name} emitted zero-weighted subtypes "
            f"(enabled, emitted error_type, token): {sorted(set(leaks))}"
        )

    @pytest.mark.parametrize("handler_name", WEIGHTED_MULTI_SUBTYPE)
    def test_battery_triggers_known_subtypes(self, handler_name):
        """Anti-vacuousness guard for the exclusion test above."""
        fired, _, _ = _sweep(handler_name)
        missing = EXPECTED_FIRED[handler_name] - set(fired)
        assert not missing, (
            f"battery no longer triggers {handler_name} subtypes "
            f"{sorted(missing)} — the zero-weight exclusion test went "
            "partially vacuous; update BATTERY"
        )

    @pytest.mark.parametrize(
        "handler_name",
        [
            pytest.param(
                name,
                marks=(
                    [
                        pytest.mark.xfail(
                            strict=True,
                            reason=(
                                f"BUG: {name}.apply() feeds zero weights "
                                "straight to rng.choices(); when every "
                                "applicable subtype at a token is "
                                "zero-weighted it raises ValueError('Total "
                                "of weights must be greater than zero') "
                                "instead of returning None. Reachable with "
                                "the shipped lorugec preset (it zeroes "
                                "function_spelling.neg_pronoun_ne_ni, so a "
                                "sentence containing 'никого' crashes "
                                "generation)."
                            ),
                        )
                    ]
                    if name in ZERO_TOTAL_CRASH_HANDLERS
                    else []
                ),
            )
            for name in WEIGHTED_MULTI_SUBTYPE
        ],
    )
    def test_all_zero_candidates_skip_instead_of_crash(self, handler_name):
        """When every applicable subtype is zeroed, apply() must return None
        (like spelling and comma_delete do), not raise from rng.choices."""
        _, _, crashes = _sweep(handler_name)
        assert not crashes, (
            f"{handler_name}.apply() crashed on zero-total subtype weights "
            f"(enabled, token, error): {sorted(set(crashes))[:5]}"
        )


# ── Invariants 3 & 4: pipeline sampling honors handler weights ──────────────


class _StaticLanguage:
    """Minimal language module: real Russian handlers, no NLP backend."""

    name = "static-test"

    def __init__(self, handlers):
        self._handlers = handlers

    def get_error_handlers(self):
        return self._handlers

    def get_error_distribution(self):
        return {}

    def get_analyzer(self, **kwargs):  # pragma: no cover - guard
        raise AssertionError("sampling tests must not need an analyzer")


def _sampling_pipeline(config: GenerationConfig) -> ErrorPipeline:
    return ErrorPipeline(_StaticLanguage(get_all_handlers()), config)


class TestPipelineSamplingHonorsWeights:
    """Bug 1 regression: every draw — length-changing included — comes from
    the weighted distribution."""

    N_DRAWS = 300

    @pytest.mark.parametrize("only", ALL_HANDLER_NAMES)
    def test_single_positive_weight_wins_every_draw(self, only):
        weights = {name: (1.0 if name == only else 0.0) for name in ALL_HANDLER_NAMES}
        pipeline = _sampling_pipeline(GenerationConfig(seed=42, error_weights=weights))
        for _ in range(self.N_DRAWS):
            handler = pipeline._sample_error_type()
            assert handler is not None
            assert handler.name == only, (
                f"weights gave 1.0 to '{only}' and 0.0 to everything else, "
                f"but _sample_error_type returned '{handler.name}'"
            )

    def test_zero_weighted_length_changing_handlers_never_drawn(self):
        """Direct regression for bug 1 (uniform draw of length-changers)."""
        length_changing = {
            name for name, cls in _handler_classes().items() if cls.changes_length
        }
        assert length_changing, "test requires length-changing handlers"
        weights = {
            name: (0.0 if name in length_changing else 1.0)
            for name in ALL_HANDLER_NAMES
        }
        pipeline = _sampling_pipeline(GenerationConfig(seed=7, error_weights=weights))
        for _ in range(2000):
            handler = pipeline._sample_error_type()
            assert handler is not None
            assert not handler.changes_length, (
                f"length-changing handler '{handler.name}' was sampled "
                "despite weight 0.0 — length-changing draws must come from "
                "the weighted distribution, not a uniform side channel"
            )


class TestLorugecPresetSampling:
    """Invariant 4: the real lorugec preset's zero weights are dead."""

    def test_zero_weighted_handlers_never_sampled(self):
        config = GenerationConfig.from_preset("ru", "lorugec")
        assert config.error_weights, "lorugec preset must define weights"

        zeroed = {k for k, v in config.error_weights.items() if v == 0.0}
        positive = {k for k, v in config.error_weights.items() if v > 0.0}
        assert zeroed, "lorugec is expected to zero-weight some handlers"
        assert positive, "lorugec must keep some handlers enabled"

        pipeline = _sampling_pipeline(config)
        seen: set[str] = set()
        for _ in range(3000):
            handler = pipeline._sample_error_type()
            assert handler is not None
            assert handler.name not in zeroed, (
                f"lorugec zero-weights '{handler.name}' but the pipeline "
                "sampled it anyway"
            )
            seen.add(handler.name)
        # Sanity: the draw really exercises the weighted distribution.
        assert len(seen) > 1
