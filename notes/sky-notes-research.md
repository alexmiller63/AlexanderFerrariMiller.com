# Sky Notes research procedure

Before a requested build, Heather checks every permanent object ID in its Calendar range. A catalogue fallback is an incomplete editorial entry, not a finished Wordy story.

Run `python tools/audit_story_research.py YEAR FIRST_WEEK LAST_WEEK --output generated/story-research-queue.json`. Use `--require-complete` for a preflight that exits unsuccessfully while any story still needs research. The check reads source stories and does not regenerate public pages.

For every missing or thin account:

1. Resolve the permanent object ID, aliases and accepted finder geometry. Search by catalogue identity as well as name; do not join objects by display labels.
2. Search and read primary sources: published research, astronomical catalogues, observatories, space agencies and documented historical scholarship. Save exact source URLs or DOIs and note which claims they support.
3. Write an original reusable story under an existing collection at `stories/<collection>/<fixed_object_id>.md`. Include an engaging heading, a short Highlights hook, and a substantial Wordy body, normally 500–800 words. Explain physical nature, discoveries and evidence, uncertainties, meaningful history, how to find it and what an observer can see. Define unfamiliar terms. Do not pad a thin account to satisfy a word count.
4. Attribute measured values and derived conclusions. Clearly distinguish Star Almanack calculations from source measurements. Credit sources near the associated paragraph. Quote only when necessary, marking quotations explicitly. Do not invent missing information or present unsettled claims as facts.
5. Keep current-week position, Moon phase, conjunctions and observing times in the weekly calculation layer. Evergreen stories must not carry last week's temporary conditions into future weeks.
6. Re-run the coverage check, inspect the full Wordy rendering and brief Highlights rendering, verify source claims and finder instructions, and save the source story in the repository for reuse. Research each object once; enrich it later when significant evidence changes.

The preflight is a structural check, not a scientific fact-check or plagiarism detector. Passing its length, paragraph and citation checks does not establish research quality; Heather must read and verify the account.

Research takes place in this conversation, as selected by Alexander. GitHub builds render saved stories; they cannot invoke this conversation's browsing tools. Do not claim that a queue entry has been researched, or that unattended research exists, merely because the preflight found it. Do not replace missing research with catalogue boilerplate.
