# Nativitas aspect interpretation library

Historical-source editorial project. Interpretations are descriptions of astrological tradition, not scientifically validated personality or medical predictions.

## Editorial policy
- Exactly one entry per unordered planetary pair and major aspect.
- The existing ten-body catalog contains 45 pairs and 225 entries; **Ceres and Pluto are on hold for the historical audit**. Do not delete existing entries solely because they are outside the current audit scope.
- Write specific, readable original interpretations; avoid repeated prefatory caveats.
- Keep Lilly, Carter, Cornell, SIMBAD, and other source names out of the interpretive narrative unless the author or source itself is the subject. Place compact, clickable bibliographic references in a **Sources** section at the bottom of the displayed interpretation.
- A single disclaimer belongs in the UI: astrology is not scientifically validated.
- Interpretive historical authorities for this audit: William Lilly, *Christian Astrology* (1647); C. E. O. Carter, *The Astrological Aspects* (1930); H. L. Cornell, *Encyclopaedia of Medical Astrology* (1933).
- Do **not** use contemporary astrology sites as interpretive authorities. Existing modern-site citations in the catalog are legacy research references, not approval evidence.
- Distinguish traditional seven-planet material from later treatments of Uranus and Neptune. Do not attribute interpretations of planets unknown in Lilly's era to Lilly.
- Cite only passages actually checked, with the edition, section, and page where ascertainable. Page numbers vary by edition. Do not imply a source supports exact wording unless checked.
- Carter often treats sextile/trine together and square/opposition together; do not invent source-specific differences that he did not establish.
- Check astronomical feasibility separately from interpretive source support.
- Status `draft-awaiting-source-verification` means **not approved for publication**. Status `reviewed-against-online-reference` is **not** evidence of verification against the three designated historical authors.
- This catalog is currently **not wired into the natal chart generator**.

## Schema
`pair`: two lowercase planet IDs in `planet_order`; `aspect`: one of five major aspects; `text`: original editorial summary; `tradition`: interpretive school; `status`: review gate; `sources`: checked citations (empty until verified).

## Audit progress and publication gate
- Editorial replacement drafts have been discussed for nine Sun/Moon-led pairs, through Moon–Mercury (37 possible-aspect drafts). These conversational drafts have **not** been committed to this catalog and are **not** finally source-verified.
- The next pair in sequence is Moon–Venus.
- Continue the remaining pairs in consolidated batches rather than requiring separate user prompts.
- Cornell's source availability is unresolved; do not manufacture page references or verification.
- The structural audit script does not authenticate citations or compare interpretation text to historical sources. Publication approval requires a separate source audit.
