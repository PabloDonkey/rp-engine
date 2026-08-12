"""The value model for scenario-side metadata.

A scenario, a world, a character and a story graph all carry free-form metadata. A value
is one string, or a list of strings. Curated scenarios already store a `tags` list, so a
plain string map was never the real shape.

Session metadata, message metadata and LLM response metadata are deliberately outside this
model. The engine writes those itself and reads them back as plain strings, so they stay
`dict[str, str]`.
"""

MetadataValue = str | list[str]
"""One metadata value: a string, or a list of strings."""

Metadata = dict[str, MetadataValue]
"""A whole metadata map, as the definition side of the domain holds it."""
