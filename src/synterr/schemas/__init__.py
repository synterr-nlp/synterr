"""Linguistic schema support for synterr.

Schemas define error taxonomies (RLC, RuBLiMP, Rozental, etc.)
and map handler subtypes to schema-specific tags.

Supports compositional schemas like RLC where:
- 35 primary tags define error types
- 3 modifiers (Miss, Extra, Transfer) combine with primary tags
- Combined tags like "Ref+Miss" are generated
"""

from synterr.schemas.loader import (
    FineGrainedTag,
    Schema,
    SchemaModifier,
    SchemaTag,
    SubtypeMapping,
    get_default_schema,
    list_schemas,
    load_schema,
)

__all__ = [
    "FineGrainedTag",
    "Schema",
    "SchemaModifier",
    "SchemaTag",
    "SubtypeMapping",
    "get_default_schema",
    "list_schemas",
    "load_schema",
]
