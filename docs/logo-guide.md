# Logo Guide

## Purpose

This document governs the selection, storage, use, and derivation of logos and social-media brand assets used by AlexanderFerrariMiller.com.

The guiding principle is simple:

> **Consistency comes from layout, sizing, spacing, and alignment — not from forcing different brands to look alike.**

Every organization owns its visual identity. We respect that identity while presenting all services as members of one coherent interface.

---

## 1. Source of Truth

Whenever an organization publishes official brand artwork, that artwork is the preferred source.

Do not redraw, approximate, recolor, distort, simplify, outline, crop, add effects to, or otherwise modify a third-party logo unless that organization's current brand guidelines explicitly permit the change.

Do not select a logo merely because it appears in an image search or third-party icon collection. When practical, verify the asset against the brand owner's current resources.

If a brand changes its official artwork, evaluate the new artwork and update the canonical source rather than modifying each use of the old asset independently.

---

## 2. Canonical Assets

Canonical vector artwork lives in:

`images/source-svg/`

The canonical SVG is the source from which purpose-specific raster derivatives are produced.

Canonical source artwork should be preserved as supplied by the brand owner whenever possible.

For PearlSom, the canonical artwork is our own controlled master artwork.

---

## 3. Derived Assets

Raster files are derivatives, not independent artwork.

Current derivative classes are:

- `-web.png` — raster asset optimized for website use when PNG is appropriate.
- `-email.png` — lightweight raster asset intended for email clients and signatures.

A derivative must preserve the approved appearance of its canonical source. Optimization may change dimensions, encoding, or compression, but must not silently redesign the logo.

When a canonical source changes, regenerate its derivatives.

Do not repair a derivative independently when the underlying problem belongs in the canonical source.

---

## 4. Presentation

Different brands do not need identical colors or internal geometry.

Visual consistency should instead be created through:

- consistent icon containers;
- appropriate displayed dimensions;
- optical rather than blindly mathematical sizing when necessary;
- consistent alignment;
- consistent spacing;
- adequate clear space;
- appropriate light- and dark-background treatment; and
- accessible links and labels.

A brand's published minimum-size and clear-space requirements override local styling preferences.

Do not enlarge, shrink, or crowd a mark beyond what its brand etiquette permits simply to make it match its neighbors.

---

## 5. Third-Party Social-Media Brands

The following services are represented using their current approved brand assets. Their own published brand guidelines remain authoritative if this document and a current brand guide ever disagree.

### Facebook

Use the current official Facebook icon supplied by Meta.

Preserve the approved Facebook colors and geometry. Do not recolor Facebook to match the site's palette.

### Instagram

Use the current official Instagram glyph supplied through Meta's brand resources.

Preserve its approved treatment, including the official gradient where that is the selected asset. Do not substitute a locally recolored version merely for visual uniformity.

### TikTok

Use current official TikTok artwork.

Preserve the distinctive approved TikTok color treatment and geometry. Do not convert it to the site's navy palette.

### YouTube

Use the official YouTube icon appropriate for a social-media icon lineup.

Preserve approved YouTube colors, proportions, and clear space.

### LinkedIn

Use the official LinkedIn `[in]` icon.

Use only LinkedIn-approved color treatments. Do not create an unofficial color variant.

### Snapchat

Use the official Snapchat Ghost mark supplied by Snap.

Do not redraw or locally reinterpret the Ghost.

### X

Use the current official X mark and an approved black or white treatment appropriate to the background.

Do not add decoration or alter its geometry merely to make it visually heavier than neighboring icons.

### WhatsApp

Use current official WhatsApp artwork supplied through Meta's brand resources.

Preserve approved colors and geometry.

### Zello

For links representing the Zello service, user, or channel, use the official Zello service/app icon appropriate to the displayed size rather than substituting an unrelated corporate mark.

Use an approved Zello color treatment and observe Zello's minimum-size guidance.

---

## 6. PearlSom

PearlSom is a social-media brand and should be treated with the same discipline and respect applied to established third-party services.

PearlSom does **not** need to imitate another network in order to fit into a social-media lineup.

Its identity should remain recognizably its own while its presentation follows the same professional conventions of sizing, spacing, clarity, and accessibility used for neighboring services.

### Canonical PearlSom Logo

The current canonical master is:

`images/source-svg/Navy-Pearl-Wave-P-Logo.svg`

The master contains the PearlSom visual identity: the navy P, pearl, wave, and approved supporting treatments.

The canonical master must not be casually redrawn or altered to solve a downstream display problem.

### PearlSom Social Icon

PearlSom may have a purpose-designed social icon derived from its established identity for use alongside Facebook, Instagram, TikTok, YouTube, LinkedIn, Snapchat, X, WhatsApp, and Zello.

The social icon should:

- remain immediately recognizable as PearlSom;
- preserve the defining P / pearl / wave identity;
- remain legible at small sizes;
- work in both light and dark presentation contexts;
- avoid unnecessary detail that disappears at icon scale; and
- remain faithful to the canonical PearlSom identity rather than becoming an unrelated secondary logo.

The social icon must be engineered deliberately. It should not be created merely by shrinking a complex logo until details disappear.

### PearlSom Approved Variants

PearlSom should eventually define and document:

- primary full-color treatment;
- approved monochrome treatment(s), if any;
- light-background treatment;
- dark-background treatment;
- minimum display size;
- clear-space requirement; and
- prohibited alterations.

Those rules should be added here when formally adopted.

---

## 7. Email Use

Email clients are less predictable than modern web browsers. Email assets therefore favor compatibility and reliability.

Use the `-email.png` derivative when a raster image is preferable for email-client compatibility.

Email derivatives should be:

- lightweight;
- sufficiently high resolution for their intended displayed size;
- visually faithful to the canonical source;
- tested against both light and dark email backgrounds where practical; and
- free of assumptions that depend on CSS masking or browser-only SVG behavior.

Do not recolor a third-party logo simply to solve dark-mode visibility. Use an approved variant or an appropriate presentation/background treatment instead.

---

## 8. Web Use

Use canonical SVG artwork directly when doing so is appropriate and compatible with the brand's rules and the site's implementation.

Use `-web.png` where a raster derivative is technically or operationally preferable.

The website must not depend on a derivative being the authoritative copy of a logo.

---

## 9. Accessibility

A logo used as a link must have an accessible name that identifies the destination or service.

Decorative duplication should not create redundant screen-reader output.

Color alone should not be the only means of communicating the purpose of a social-media link.

---

## 10. Replacement Procedure

When replacing a social-media logo:

1. Find the brand owner's current official asset and guidelines.
2. Verify that the selected mark is appropriate for our use case.
3. Record any important color, clear-space, minimum-size, or alteration restrictions in this guide.
4. Place the approved canonical SVG in `images/source-svg/`.
5. Preserve a stable filename where practical so consumers do not need unnecessary changes.
6. Regenerate `-web.png` and `-email.png` derivatives as needed.
7. Test website presentation.
8. Test email presentation where the asset is used in signatures.
9. Test light and dark backgrounds where applicable.
10. Do not delete or overwrite source material blindly; confirm the replacement is correct first.

---

## 11. Engineering Rule

Consumers should reference canonical or purpose-specific assets predictably rather than embedding independent copies of logo artwork throughout the site.

A future improvement to a canonical logo should propagate through regeneration and normal asset references, not through a scavenger hunt across HTML, CSS, email signatures, and generated documents.

---

## 12. Governing Principle

**Fit in by behaving professionally, not by copying everyone else.**

That rule applies equally to PearlSom and to every third-party brand represented beside it.
