# Verified greatest-eclipse baseline — 2026-10-21

This recovery snapshot preserves Star Almanack's verified solar greatest-eclipse
timing backend. It does not certify contact times, lunar-eclipse calculations,
classification, or the times currently displayed on published pages.

Verified source commit: `efc591a3bb1f2b0e05c7b9aa39bf0bbef075c989`.

The backend is `besselian_eclipse_engine.py`, not the older `eclipse_engine.py`.
It computes the shadow-axis minimum without reading a reference eclipse time,
using apparent Sun and Moon positions, a local DE440s kernel, and JDTDB internally.
Validation compares calculated TT directly with NASA TD labels. The legacy
`*_utc` reference fields must not be treated as civil UTC for these comparisons.

## Preserved inputs

- `besselian_eclipse_engine.py`: the verified backend.
- `.cache/skyfield/de440s.bsp`: the kernel, tracked in this Git snapshot.
- `eclipse-validation-cases.yaml`: nine independent, whole-second NASA targets.
- `THIRD-PARTY-LICENSES.md`: retained dependency license notice.
- `.github/workflows/diagnose-open-besselian.yml`: the original production audit.
- `verify.py`: the same audit, extracted for repeatable local execution.
- `requirements.txt`: the dependency versions used for the local verification.
- `verified-results.txt`: the complete fresh audit output.

The pinned eclipse-calc source revision is
`23853a8f9e0d1a25e026203207aca16de1d7bb31`. Dependencies can be installed from
the requirements file; the astronomical calculation itself makes no downloads.
No recovery file or runtime dependency is placed in a `Historical` folder.

## Repeat verification

Use Python 3.12 from the repository root:

```sh
python3.12 -m venv /tmp/eclipse-baseline-env
/tmp/eclipse-baseline-env/bin/python -m pip install -r docs/eclipse-baseline-2026-10-21/requirements.txt
/tmp/eclipse-baseline-env/bin/python docs/eclipse-baseline-2026-10-21/verify.py
```

The check exits unsuccessfully if the largest difference exceeds 1 second.
The recorded result is 9 cases, mean absolute difference 0.284 seconds,
maximum absolute difference 0.454 seconds. The references have whole-second
resolution; this establishes agreement within their rounding precision, not
an independently measured absolute accuracy of 0.454 seconds.

## Integrity

SHA-256 checksums of the verified files:

```text
c89e417a30cc2a4ad129235eab830047c7f55b98cbeaeb5117ac62df3ea46df8  besselian_eclipse_engine.py
c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2  .cache/skyfield/de440s.bsp
c6563ab3ca256493bcd70668f476c76192685c78deeece1414328e7f42cda849  eclipse-validation-cases.yaml
f1fb2cc421c672233514eaf11d739ffb506cac9b0c364d47ff206531ffbf645f  THIRD-PARTY-LICENSES.md
```

Keep the recovery branch `eclipse-baseline-2026-10-21` at this saved state.
Perform further development on other branches. This snapshot does not change
the main branch or publish website output.
