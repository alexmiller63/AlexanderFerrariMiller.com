# Second-Magnitude Bright-Star Layer

## Purpose

Add an observer-first bright-star layer to the Star Almanack so more calendar dates carry a useful naked-eye stellar observation without replacing the complete α/β Bayer catalog.

## Inclusion rule

Include every stellar system whose **representative maximum apparent Johnson V magnitude is +2.50 or brighter** (numerically `Vmax <= 2.50`). The Sun is excluded.

The boundary, not an arbitrary object count, defines the layer. A star may qualify even when its mean or catalog snapshot magnitude is fainter than +2.50 if a reproducible representative maximum reaches the threshold.

## Brightness policy

- Use representative maximum V for catalog membership and ordering.
- Do not rank by a one-off exceptional historical observation.
- Preserve exceptional maxima, minima, eclipses, eruptions, and major dimming episodes in star notes under **Outbursts and exceptional brightness**.
- For stable stars, the catalog V magnitude may serve as the representative value when no meaningful variability correction is required.
- For multiple systems, use the naked-eye system brightness when that is the observer-relevant quantity; retain component information in notes/source fields when needed.

## Calendar placement

Use the existing Star Almanack observer-first best-visibility rule:

`α☉ = αobject − 9h`

Solve the apparent solar right ascension for the annual instant, round to the nearest civil date, and place the bright-star note on that date in ISO 2026.

## Relationship to other layers

- Messier layer: all M1–M110.
- Bayer layer: complete audited α/β designations, including justified numbered components.
- Second-magnitude layer: all stars meeting `representative Vmax <= +2.50`, regardless of Bayer letter.

A star already present in the Bayer layer is not a duplicate astronomical object; the bright-star layer is an editorial highlight layer and should enrich the same calendar entry rather than create confusing duplicate prose.

## Provenance and validation

The baseline source may be the pinned HYG v4.1 catalog for coordinates and stable visual magnitudes. Variable-star membership near the +2.50 boundary requires an auditable override/source table rather than silently trusting a single catalog snapshot magnitude.

The final layer is not considered complete until:

1. every baseline HYG object at V <= +2.50 has been considered;
2. variable stars whose representative maximum crosses the threshold have been audited and added when justified;
3. duplicates/multiple-system identities are reconciled for naked-eye use;
4. every included object has one best-visibility date;
5. the existing 15-case visibility regression remains 15/15 PASS;
6. ISO 2026 boundary dates are handled correctly.
