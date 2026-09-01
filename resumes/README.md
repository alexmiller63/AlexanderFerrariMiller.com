# Resume Generation

The files in this directory use Markdown source files as the source of truth. Generated resume formats are produced by `tools/generate-resumes.py` through the GitHub Actions workflow `.github/workflows/generate-resumes.yaml`.

## Source files

Each resume has a source file named:

```text
<name>-resume.md
```

Shared contact information comes from:

```text
header.txt
```

Do not edit generated HTML, PDF, DOCX, ODT, or TXT files as the source of a resume. Edit the Markdown source, then regenerate the outputs.

## Selecting resumes to generate

The workflow does **not** regenerate every resume. The queue is:

```text
generate-list.txt
```

Add one resume stem per line, without the `.md` extension. For example:

```text
bartender-resume
performance-resume
```

Blank lines and lines beginning with `#` are ignored. Inline comments after `#` are also ignored.

For every listed stem, the workflow verifies that `resumes/<stem>.md` exists. If a listed source does not exist, the workflow fails rather than silently generating the wrong set of files.

An empty generation list is intentional: it means that no resumes are currently queued for generation. If **Generate Resumes** is run while the list is empty, the workflow completes without generating or uploading an artifact and displays a warning reminding the user to add one or more resume stems to `resumes/generate-list.txt`, commit the change, and run the workflow again.

## Running the workflow

Run the GitHub Actions workflow **Generate Resumes** manually with `workflow_dispatch`.

For each resume in `generate-list.txt`, the workflow generates exactly these 5 formats:

- HTML (`.html`)
- PDF (`.pdf`)
- Microsoft Word (`.docx`)
- OpenDocument Text (`.odt`)
- Plain text (`.txt`)

Only those selected output files are placed in the workflow artifact. The artifact is named:

```text
selected-resumes
```

Download the artifact ZIP, extract it, and upload/replace the generated files in the repository. Git records changes based on file contents, not filesystem modification dates.

## Automatic queue reset

After generation, packaging, and artifact upload succeed, the workflow empties `generate-list.txt` and commits that reset to the repository. This makes the list a one-run queue and prevents a later run from accidentally regenerating the previous set of resumes.

The reset happens only after the preceding workflow steps succeed. If generation or packaging fails, the list remains populated so the requested set is preserved for troubleshooting and retry.

## Normal procedure

1. Edit the appropriate `<name>-resume.md` source file.
2. Add that resume stem to `generate-list.txt`.
3. Commit the source and generation-list changes.
4. Run **Generate Resumes** in GitHub Actions.
5. Confirm that the workflow succeeds.
6. Download and extract the `selected-resumes` artifact.
7. Upload/replace the generated files in `resumes/` and commit them.
8. Confirm that `generate-list.txt` was automatically reset to empty by the workflow.

If several resume sources changed, list all of their stems before running the workflow. Only those resumes will be regenerated and included in the artifact.
