"""Configuration management for synterr."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any

import yaml


def load_preset(language: str, preset_name: str) -> dict[str, Any]:
    """Load a preset configuration by name.

    Args:
        language: Language code (e.g., 'ru', 'russian')
        preset_name: Preset name (e.g., 'rulec', 'gera', 'balanced')

    Returns:
        Configuration dict with weights and settings

    Raises:
        FileNotFoundError: If preset doesn't exist
    """
    # Normalize language code
    lang_dir = _normalize_language(language)

    # Try package resources first
    try:
        with importlib.resources.files("synterr.configs").joinpath(
            f"{lang_dir}/{preset_name}.yaml"
        ).open() as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, TypeError):
        pass

    # Fall back to file path (for development)
    config_dir = Path(__file__).parent / lang_dir
    config_path = config_dir / f"{preset_name}.yaml"

    if not config_path.exists():
        available = list_presets(language)
        raise FileNotFoundError(
            f"Preset '{preset_name}' not found for language '{language}'. "
            f"Available: {', '.join(available) or '(none)'}"
        )

    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(path: str | Path) -> dict[str, Any]:
    """Load configuration from a YAML file.

    Args:
        path: Path to YAML config file

    Returns:
        Configuration dict
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_presets(language: str) -> list[str]:
    """List available presets for a language.

    Args:
        language: Language code

    Returns:
        List of preset names (without .yaml extension)
    """
    lang_dir = _normalize_language(language)

    # Try package resources
    try:
        pkg_path = importlib.resources.files("synterr.configs") / lang_dir
        if pkg_path.is_dir():
            return [
                p.name.removesuffix(".yaml")
                for p in pkg_path.iterdir()
                if p.name.endswith(".yaml")
            ]
    except (TypeError, AttributeError):
        pass

    # Fall back to file path
    config_dir = Path(__file__).parent / lang_dir
    if config_dir.exists():
        return [p.stem for p in config_dir.glob("*.yaml")]

    return []


def get_default_preset(language: str) -> str:
    """Get the default preset name for a language.

    Args:
        language: Language code

    Returns:
        Default preset name
    """
    # Default presets per language
    defaults = {
        "russian": "rulec",
        "ru": "rulec",
    }
    return defaults.get(language.lower(), "balanced")


def _normalize_language(language: str) -> str:
    """Normalize language code to directory name."""
    mapping = {
        "ru": "russian",
        "russian": "russian",
    }
    return mapping.get(language.lower(), language.lower())
