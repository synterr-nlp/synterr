"""Override semantics for GenerationConfig factory methods.

A caller default of None must never clobber an explicit YAML value —
the config-binding bug class (e.g. the CLI's --depparse default silently
disabling a preset's `use_depparse: true`).
"""

from synterr.core.pipeline import GenerationConfig


class TestFromDictOverrides:
    def test_none_override_keeps_yaml_value(self):
        cfg = GenerationConfig._from_dict(
            {"use_depparse": True, "backend": "natasha", "schema": "rozental"},
            use_depparse=None,
            backend=None,
            schema=None,
        )
        assert cfg.use_depparse is True
        assert cfg.backend == "natasha"
        assert cfg.schema == "rozental"

    def test_explicit_false_still_overrides(self):
        cfg = GenerationConfig._from_dict(
            {"use_depparse": True}, use_depparse=False
        )
        assert cfg.use_depparse is False

    def test_explicit_true_overrides_yaml_false(self):
        cfg = GenerationConfig._from_dict(
            {"use_depparse": False}, use_depparse=True
        )
        assert cfg.use_depparse is True

    def test_yaml_absent_falls_back_to_default(self):
        cfg = GenerationConfig._from_dict({}, use_depparse=None)
        assert cfg.use_depparse is False
