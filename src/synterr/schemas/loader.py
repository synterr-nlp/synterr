"""Schema loader for synterr linguistic taxonomies.

Supports compositional schemas like RLC where:
- 35 primary tags define error types
- 3 modifiers (Miss, Extra, Transfer) combine with primary tags
- Combined tags like "Ref+Miss" or "Hyphen+Del" are generated
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SchemaTag:
    """A single tag in a linguistic schema."""

    name: str
    description: str = ""
    detection_category: str = "OTHER"


@dataclass
class SchemaModifier:
    """A modifier that combines with primary tags."""

    name: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class FineGrainedTag:
    """An L2 fine-grained tag in a hierarchical schema (e.g., Rozental)."""

    name: str
    parent: str
    description: str = ""
    paras: str = ""
    l2_applicability: str = ""  # full | partial | none — does the native Rozental § describe the L2 error
    l2_note: str = ""


@dataclass
class SubtypeMapping:
    """Mapping from handler subtype to schema tag(s).

    Attributes:
        primary: Primary schema tag name
        modifier: Optional modifier (Miss, Extra, Transfer)
        secondary: Additional tags (for multi-label)
    """

    primary: str
    modifier: str | None = None
    secondary: list[str] = field(default_factory=list)
    l2_tag: str | None = None

    def get_full_tag(self) -> str:
        """Get the full tag name including modifier."""
        if self.modifier:
            return f"{self.primary}+{self.modifier}"
        return self.primary


@dataclass
class Schema:
    """Loaded schema definition.

    A schema defines a linguistic error taxonomy (e.g., RLC, RuBLiMP)
    and maps handler subtypes to schema tags.

    Supports compositional schemas with primary tags and modifiers.
    """

    name: str
    version: str
    description: str
    detection_categories: dict[str, str]
    primary_tags: dict[str, SchemaTag]
    modifiers: dict[str, SchemaModifier]
    mappings: dict[str, SubtypeMapping]
    fine_grained_tags: dict[str, FineGrainedTag] = field(default_factory=dict)

    # For backward compatibility, also expose as 'tags'
    @property
    def tags(self) -> dict[str, SchemaTag]:
        """Alias for primary_tags (backward compatibility)."""
        return self.primary_tags

    def get_mapping(self, subtype: str) -> SubtypeMapping | None:
        """Get full mapping for a handler subtype."""
        return self.mappings.get(subtype)

    def get_tag_for_subtype(self, subtype: str) -> str | None:
        """Get primary schema tag for a handler subtype.

        Args:
            subtype: Handler subtype name (e.g., 'vowel_reduction')

        Returns:
            Primary schema tag (without modifier), or None if not mapped
        """
        mapping = self.mappings.get(subtype)
        return mapping.primary if mapping else None

    def get_full_tag_for_subtype(self, subtype: str) -> str | None:
        """Get full schema tag including modifier.

        Args:
            subtype: Handler subtype name

        Returns:
            Full tag like "Ref+Miss" or "Ortho", or None if not mapped
        """
        mapping = self.mappings.get(subtype)
        return mapping.get_full_tag() if mapping else None

    def get_modifier_for_subtype(self, subtype: str) -> str | None:
        """Get modifier for a handler subtype.

        Args:
            subtype: Handler subtype name

        Returns:
            Modifier name (Miss, Extra, Transfer) or None
        """
        mapping = self.mappings.get(subtype)
        return mapping.modifier if mapping else None

    def get_l2_tag_for_subtype(self, subtype: str) -> str | None:
        """Get L2 fine-grained tag for a handler subtype.

        Args:
            subtype: Handler subtype name

        Returns:
            L2 tag name (e.g., "sp_root_checked") or None
        """
        mapping = self.mappings.get(subtype)
        if mapping and mapping.l2_tag and mapping.l2_tag in self.fine_grained_tags:
            return mapping.l2_tag
        return None

    def get_detection_category(self, subtype: str) -> str:
        """Get detection category for a handler subtype.

        The detection category (SPELL, MORPH, OTHER, etc.) comes from
        the primary schema tag.

        Args:
            subtype: Handler subtype name

        Returns:
            Detection category string, defaults to "OTHER"
        """
        tag_name = self.get_tag_for_subtype(subtype)
        if tag_name and tag_name in self.primary_tags:
            return self.primary_tags[tag_name].detection_category
        return "OTHER"

    def resolve_modifier_alias(self, alias: str) -> str | None:
        """Resolve a modifier alias to its canonical name.

        Args:
            alias: Alias like "Del" or "Ins"

        Returns:
            Canonical modifier name like "Miss" or "Extra", or None
        """
        # Check if it's already a canonical name
        if alias in self.modifiers:
            return alias

        # Check aliases
        for mod_name, mod in self.modifiers.items():
            if alias in mod.aliases:
                return mod_name

        return None

    def get_coverage_report(self, available_subtypes: set[str]) -> dict[str, Any]:
        """Report which schema tags are covered by available handlers.

        Args:
            available_subtypes: Set of subtypes from registered handlers

        Returns:
            Dict with coverage statistics
        """
        mapped_subtypes = set(self.mappings.keys())
        covered_subtypes = mapped_subtypes & available_subtypes

        # Find which primary tags are covered
        covered_tags = set()
        for subtype in covered_subtypes:
            mapping = self.mappings.get(subtype)
            if mapping:
                covered_tags.add(mapping.primary)

        return {
            "schema_name": self.name,
            "total_tags": len(self.primary_tags),
            "covered_tags": len(covered_tags),
            "coverage_percent": round(
                100 * len(covered_tags) / len(self.primary_tags), 1
            )
            if self.primary_tags
            else 0,
            "covered_tag_names": sorted(covered_tags),
            "uncovered_tag_names": sorted(set(self.primary_tags.keys()) - covered_tags),
            "mapped_subtypes": sorted(covered_subtypes),
            "unmapped_subtypes": sorted(available_subtypes - mapped_subtypes),
            "modifiers_used": sorted(
                {
                    m.modifier
                    for s, m in self.mappings.items()
                    if s in covered_subtypes and m.modifier
                }
            ),
        }


def _get_builtin_schema_path(name: str) -> Path | None:
    """Get path to a built-in schema file."""
    schema_dir = Path(__file__).parent / "data"
    path = schema_dir / f"{name}.yaml"
    return path if path.exists() else None


def _parse_tags(data: dict, key: str = "tags") -> dict[str, SchemaTag]:
    """Parse tags from schema data.

    Supports both 'tags' (flat) and 'primary_tags' (compositional) keys.
    """
    tags = {}
    tag_data = data.get(key, {})

    for tag_name, tag_info in tag_data.items():
        if isinstance(tag_info, dict):
            tags[tag_name] = SchemaTag(
                name=tag_name,
                description=tag_info.get("description", ""),
                detection_category=tag_info.get("detection_category", "OTHER"),
            )
        else:
            # Simple format: tag_name: detection_category
            tags[tag_name] = SchemaTag(
                name=tag_name,
                detection_category=str(tag_info) if tag_info else "OTHER",
            )

    return tags


def _parse_modifiers(data: dict) -> dict[str, SchemaModifier]:
    """Parse modifiers from schema data."""
    modifiers = {}
    mod_data = data.get("modifiers", {})

    for mod_name, mod_info in mod_data.items():
        if isinstance(mod_info, dict):
            modifiers[mod_name] = SchemaModifier(
                name=mod_name,
                description=mod_info.get("description", ""),
                aliases=mod_info.get("aliases", []),
            )
        else:
            modifiers[mod_name] = SchemaModifier(
                name=mod_name,
                description=str(mod_info) if mod_info else "",
            )

    return modifiers


def _parse_fine_grained_tags(data: dict) -> dict[str, FineGrainedTag]:
    """Parse fine-grained (L2) tags from schema data."""
    tags = {}
    fg_data = data.get("fine_grained_tags", {})

    for tag_name, tag_info in fg_data.items():
        if isinstance(tag_info, dict):
            tags[tag_name] = FineGrainedTag(
                name=tag_name,
                parent=tag_info.get("parent", ""),
                description=tag_info.get("description", ""),
                paras=tag_info.get("paras", ""),
                l2_applicability=tag_info.get("l2_applicability", ""),
                l2_note=tag_info.get("l2_note", ""),
            )

    return tags


def _parse_mappings(data: dict) -> dict[str, SubtypeMapping]:
    """Parse handler subtype mappings.

    Supports both flat format (for backward compatibility):
        vowel_reduction: [Ortho, Misspell]
        vowel_reduction: Ortho

    And compositional format:
        vowel_reduction:
            primary: Ortho
            modifier: null
        word_omission:
            primary: Syntax
            modifier: Miss
    """
    mappings = {}
    map_data = data.get("mappings", {})

    for subtype, mapping_info in map_data.items():
        if isinstance(mapping_info, dict):
            # Compositional format
            mappings[subtype] = SubtypeMapping(
                primary=mapping_info.get("primary", ""),
                modifier=mapping_info.get("modifier"),
                secondary=mapping_info.get("secondary", []),
                l2_tag=mapping_info.get("l2_tag"),
            )
        elif isinstance(mapping_info, list):
            # Flat list format: [primary, secondary1, secondary2]
            mappings[subtype] = SubtypeMapping(
                primary=mapping_info[0] if mapping_info else "",
                secondary=mapping_info[1:] if len(mapping_info) > 1 else [],
            )
        elif isinstance(mapping_info, str):
            # Simple string format
            mappings[subtype] = SubtypeMapping(primary=mapping_info)
        elif mapping_info is not None:
            mappings[subtype] = SubtypeMapping(primary=str(mapping_info))
        # Skip None values - they indicate unmapped subtypes

    return mappings


def load_schema(name_or_path: str) -> Schema:
    """Load a schema by name or file path.

    Args:
        name_or_path: Either a built-in schema name ('synterr', 'rlc')
                      or a path to a custom YAML schema file

    Returns:
        Loaded Schema instance

    Raises:
        ValueError: If schema not found
        yaml.YAMLError: If schema file is invalid
    """
    # Check for built-in schema
    builtin_path = _get_builtin_schema_path(name_or_path)
    if builtin_path:
        path = builtin_path
    elif Path(name_or_path).exists():
        path = Path(name_or_path)
    else:
        available = list_schemas()
        raise ValueError(
            f"Schema not found: {name_or_path}. Available: {', '.join(available)}"
        )

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Parse primary tags - support both 'primary_tags' and 'tags' keys
    if "primary_tags" in data:
        primary_tags = _parse_tags(data, "primary_tags")
    else:
        primary_tags = _parse_tags(data, "tags")

    # Parse modifiers
    modifiers = _parse_modifiers(data)

    # Parse mappings
    mappings = _parse_mappings(data)

    # Parse fine-grained (L2) tags
    fine_grained_tags = _parse_fine_grained_tags(data)

    return Schema(
        name=data.get("name", Path(path).stem),
        version=data.get("version", "1.0"),
        description=data.get("description", ""),
        detection_categories=data.get("detection_categories", {}),
        primary_tags=primary_tags,
        modifiers=modifiers,
        mappings=mappings,
        fine_grained_tags=fine_grained_tags,
    )


def list_schemas() -> list[str]:
    """List available built-in schema names.

    Returns:
        List of schema names (without .yaml extension)
    """
    schema_dir = Path(__file__).parent / "data"
    if not schema_dir.exists():
        return []
    return sorted(p.stem for p in schema_dir.glob("*.yaml"))


def get_default_schema() -> str:
    """Get the default schema name.

    Returns:
        'synterr' - the default backward-compatible schema
    """
    return "synterr"
