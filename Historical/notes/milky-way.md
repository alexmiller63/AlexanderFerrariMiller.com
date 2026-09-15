# Star Almanack Notes — Milky Way

## 2026-09-15 — Named Milky Way regions and deterministic rendering

### Geometry and region model

The Vieira `ol1` boundary remains the authoritative strict Milky Way boundary. Named Milky Way regions are irregular subsets cut from that strict boundary; they are **regions**, not sectors, and the named regions are not required to reconstruct or partition the entire Milky Way.

### Brightness validation

Axel Mellinger optical-survey data obtained through NASA SkyView is used as numerical validation/rendering data rather than as copied imagery.

The current fixed prominence threshold is **108.0** on the native Mellinger/SkyView image-intensity scale. The 2026-09-15 validation cleanly separated the selected bright anchors from the faint controls:

- bright minimum: 122.0
- faint maximum: 94.0
- fixed threshold: 108.0
- fixed threshold separates validation set: true

The threshold does not redefine the authoritative Vieira `ol1` Milky Way boundary. It is used to identify/validate visually prominent named regions within that geometry.

### Deterministic Milky Way artwork

Milky Way artwork should be generated deterministically from numerical astronomical data rather than by copying survey imagery or asking a generative image model to imitate a source image. Numerical position and brightness information may be sampled into a sky grid and rendered as an original continuous brightness field. Rendering choices may make the result attractive and atlas-like, but the astronomical structure must remain traceable to the underlying data.

Keep the factual Milky Way brightness field and boundary/annotation geometry as separate layers so visual styling can evolve without changing region membership.

### Named-region figure specification

Each named Milky Way region is displayed as its own titled astronomical figure over the deterministic Milky Way rendering.

- **Constellation stick figures:** blue.
- **Asterism stick figures:** green.
- **Official IAU constellation boundaries:** white.
- **Asterism boundaries:** not displayed. Asterisms are star patterns and have no official IAU-style sky boundary.

Any computational geometry used elsewhere to derive an asterism center from its member stars is an internal construction and must not be presented as an official or displayed asterism boundary.
