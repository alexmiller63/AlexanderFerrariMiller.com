# Ten-story publication handoff

**Current state (2026-10-14):** Ten revised manuscripts exist in `research/editorial-drafts/`: `alpheratz-review.md` and `2-review.md` through `10-review.md`. This branch also includes source-check notes and the batch review. The originals are untouched.

## Publication blockers, not writing blockers

The production gate `tools/luna_publication_decision.py` requires independent editorial, scientific and finder approvals; it also evaluates raw pilot narrative, numeric and SVG reports. The ten **revised** manuscripts are separate from those original pilot inputs. Therefore rerunning the existing gate without first integrating the revisions will misleadingly report the original problems as though no corrections had occurred.

**Do not** set approval booleans merely to make the gate green, or copy edited stories into live paths without checking current pages. The Finder geometry must be checked for each star.

## Concrete integration sequence

1. Map each revised manuscript to its canonical publication path via `research/luna-pilot-candidates.json` and the importer; preserve published originals and links.
2. Make the editorial pipeline read revised manuscripts as its source, then re-run narrative and numeric checks **against those revisions**.
3. Independently verify stellar identities, physical claims and observational directions, including finder coordinates. Keep a per-story evidence ledger.
4. Generate/repair missing Finder charts and verify geometry independently.
5. Record real sign-offs in `research/luna-publication-approvals.json`; publish approved stories only. Others remain pending with explicit blockers.
6. Run the staging workflow and verify published links and page content.

## Verified work so far

- Alpheratz: Kochukhov et al. (2007) mercury-abundance mapping independently checked.
- Caph, Algenib, Gamma Cassiopeiae, Segin: catalog and literature corrections recorded in `scientific-source-check-ledger.md`.
- Ruchbah, Xi Ceti and Gamma Ceti: targeted corrections committed, but current period/separation and finder geometry remain to be confirmed.
- Schedar and Polaris: rewritten conservatively; final independent physical-data checks pending.

**No publication or approval claimed.** This handoff exists to prevent redoing the writing while the integration and Finder work proceed.
