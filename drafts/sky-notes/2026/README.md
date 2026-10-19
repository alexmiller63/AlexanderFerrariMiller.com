# 2026 Sky Notes — draft preservation policy

Status: planning and draft only. No astronomical verification or proofreading is implied.

## Existing architecture (authoritative)
- Permanent identities are numeric `fixed_object_id` values in `database/fixed-objects.json`.
- Evergreen source stories already live at `stories/<collection>/<fixed_object_id>.md` and are read by `tools/fixed_object_stories.py`.
- Existing collections: alpha-stars, beta-stars, special-stars, messier, caldwell, finest.
- Example: Pleiades = fixed_object_id **594**, existing curated story `stories/special-stars/594.md`. M45 is a catalogue designation, **not** the internal ID.
- The weekly Sky Notes generator links evergreen stories; week-specific positions and conditions belong in the weekly calculation layer.
- Preserve all existing completed stories and status flags. Do not downgrade or replace them.

## Draft policy
- There is **no fixed six-stories-per-week quota**. Choose coverage from existing calendar objects and editorial merit.
- First inventory existing story coverage and identify missing/thin entries using `tools/audit_story_research.py` before creating new prose.
- Draft only for an existing registry ID and valid existing collection. Store an unpublished draft in `drafts/sky-notes/objects/<collection>/<fixed_object_id>.md` until editorial integration, with explicit `fixed_object_id`, hed, dek, body and `status: draft-unverified`.
- Do not overwrite any existing draft or published source automatically. If a story exists, preserve it and report the collision for editorial review.
- Do not set `research_checked`, `finder_checked`, `publication_checked`, or `status: complete` without the corresponding checks.
- Keep evergreen prose independent of 2026 and 2027. Weekly notes reference the fixed ID, rather than copying prose.
- Commit each new draft separately; fetch it back and compare its content. Resume from repository files, not conversation history.
- Derive any progress report from actual source/draft files, not an assumed 318-story target.
- Avoid modifying `main`, the live pages, the existing story loader or the published story sources during setup.
- Periodically make an independent backup in addition to Git history.

## Recovery and integration
1. Locate a draft by numeric fixed ID and collection; confirm it exists in the registry.
2. Review and verify it separately when ready.
3. Integrate into the existing `stories/<collection>/<fixed_object_id>.md` contract only after explicit editorial review, without silently replacing an existing story.
4. Run existing tests and rendering checks before publishing.

The earlier week-based `W##/story-##.md` proposal was superseded before any such files were created. Week 1 previously discussed stories have not been imported by this setup.
