# Star Almanack Bug Fix Log

Ongoing log of bugs, bug state, fixes, and resolutions.

Use this file for defect tracking and bug-fix work. Keep architectural discussions and design notes in `notes.md`.

## Logging rules

- Append new bugs and discoveries; do not replace prior history.
- Give each bug a stable identifier.
- Record the bug state as it changes.
- Record the affected component, observed behavior, diagnosis, fix, verification, and resolution when known.
- Preserve failed fixes and regressions as part of the history.
- A bug is not resolved merely because code was changed; record the verification that established the resolution.
- Fix generators and sources rather than patching generated output whenever the defect originates upstream.

## Bug states

Use: **Open**, **Diagnosing**, **Fix in progress**, **Fixed — awaiting verification**, **Resolved**, **Regressed**, or **Deferred**.

## Entries

<!--
### BUG-001 — Short descriptive title

**State:** Open
**Discovered:** YYYY-MM-DD
**Component:** component or workflow

**Observed:** What is wrong.

**Diagnosis:** Root cause or current diagnostic evidence.

**Fix:** What was changed, including commit when available.

**Verification:** What was checked and the result.

**Resolution:** Final outcome, or "Pending" while unresolved.

**History:**
- YYYY-MM-DD — State change or significant discovery.
-->
