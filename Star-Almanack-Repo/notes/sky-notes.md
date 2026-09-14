# Star Almanack Notes — Sky Notes

## 2026-09-13 — Descriptor-first Sky Notes architecture

Sky Notes use a descriptor-first architecture. The machine-readable descriptor is the source of truth; human-readable prose is a presentation derived from that structured descriptor. The system must not reconstruct machine-readable data by parsing the prose afterward.

For a typical weekly Sky Note, target approximately 3–4 descriptors rendered inline as human-readable explanatory prose, plus approximately 5–6 additional clickable links to relevant descriptors. This is a density target rather than a requirement to pad a note with weak or duplicate material.

Each inline descriptor retains its underlying machine-readable descriptor even when presented to the reader as prose. Clickable descriptor links route directly to machine-readable descriptor records, not merely to human-readable glossary pages.

Conceptually, the presentation is:

**machine-readable descriptor → human-readable prose → machine-readable descriptor**

The structured descriptor layer should also be reusable by downstream presentation systems, including Sky Note artwork generation. Human-readable prose is never the canonical data source.

This descriptor system is distinct from the weekly artwork descriptor. A Sky Note may contain many object/concept descriptors and descriptor links while also carrying a separate structured artwork descriptor for its eventual inline graphic.
